"""Internal inference callback."""

from __future__ import annotations

from db import create_db, embedding_literal
from http_util import json_response, parse_json


async def handle_internal(env, method: str, subpath: str, request, _user_id: str | None):
    if method == "POST" and subpath == "inference-callback":
        return await inference_callback(env, request)
    return json_response({"detail": "Not found"}, 404)


async def inference_callback(env, request):
    payload = await parse_json(request)
    results = payload.get("results") or []
    batch_id = payload.get("batch_id")
    similarity_threshold = float(getattr(env, "SIMILARITY_THRESHOLD", None) or "0.35")
    max_distance = 1.0 - similarity_threshold

    print(f"Received inference callback for batch: {batch_id}. Images count: {len(results)}")

    db = create_db(env.DATABASE_URL)
    try:
        count_row = db.fetchone("SELECT COUNT(*)::int AS count FROM face_embeddings")
        print(f"DEBUG: total face_embeddings visible to this session: {count_row['count']}")

        for item in results:
            photo_id = item.get("photo_id")
            if not photo_id:
                continue

            photo = db.fetchone(
                "SELECT id, owner_id FROM photos WHERE id = %s::uuid",
                (photo_id,),
            )
            if not photo:
                print(f"Warning: Photo {photo_id} not found in database.")
                continue

            for face in item.get("faces") or []:
                bbox = face.get("bbox") or {}
                embedding = face.get("embedding") or []
                confidence = face.get("confidence", 1.0)
                if len(embedding) != 512:
                    continue

                emb_lit = embedding_literal(embedding)
                match = db.fetchone(
                    """
                    SELECT user_id, (embedding <=> %s::vector) AS distance
                    FROM face_embeddings
                    WHERE embedding <=> %s::vector <= %s
                    ORDER BY distance ASC
                    LIMIT 1
                    """,
                    (emb_lit, emb_lit, max_distance),
                )

                if match:
                    matched_user_id = str(match["user_id"])
                    distance = float(match["distance"])
                    print(
                        f"Matched face in photo {photo_id} to user {matched_user_id} "
                        f"(distance: {distance:.4f})"
                    )
                    xmin = bbox.get("xmin", bbox.get("x"))
                    ymin = bbox.get("ymin", bbox.get("y"))
                    xmax = bbox.get("xmax")
                    ymax = bbox.get("ymax")
                    xmin_val = xmin if xmin is not None else 0
                    ymin_val = ymin if ymin is not None else 0
                    width = (xmax - xmin) if xmax is not None and xmin is not None else 0.1
                    height = (ymax - ymin) if ymax is not None and ymin is not None else 0.1

                    db.execute(
                        """
                        INSERT INTO photo_tags (
                            photo_id, user_id, bbox_x, bbox_y, bbox_width, bbox_height,
                            confidence, source
                        )
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, 'auto')
                        """,
                        (photo_id, matched_user_id, xmin_val, ymin_val, width, height, confidence),
                    )
                    db.execute(
                        """
                        INSERT INTO notifications (user_id, type, photo_id, actor_user_id, is_read)
                        VALUES (%s::uuid, 'tagged_in_photo', %s::uuid, %s::uuid, false)
                        """,
                        (matched_user_id, photo_id, str(photo["owner_id"])),
                    )
                else:
                    closest = db.fetchone(
                        """
                        SELECT user_id, (embedding <=> %s::vector) AS distance
                        FROM face_embeddings
                        ORDER BY distance ASC
                        LIMIT 1
                        """,
                        (emb_lit,),
                    )
                    if closest:
                        closest_sim = 1.0 - float(closest["distance"])
                        print(
                            f"No match found for face in photo {photo_id} "
                            f"(closest was user {closest['user_id']}, similarity: {closest_sim:.4f})"
                        )
                    else:
                        print(f"No match found for face in photo {photo_id} (no embeddings in DB at all)")

            db.execute(
                """
                UPDATE photos
                SET status = 'processed', processed_at = NOW(), batch_id = %s::uuid
                WHERE id = %s::uuid
                """,
                (batch_id, photo_id),
            )

        return json_response({"acknowledged": True})
    finally:
        db.close()
