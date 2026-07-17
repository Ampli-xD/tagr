"""Photo upload and tagging routes."""

from __future__ import annotations

import json
import math
import random
import uuid
from datetime import datetime, timezone

from batcher import enqueue_photo
from db import create_db, embedding_literal
from http_util import json_response, parse_json, parse_multipart
from storage import get_image_url, upload_image


async def handle_photos(env, method: str, subpath: str, request, user_id: str | None):
    parts = [p for p in subpath.split("/") if p]

    if method == "POST" and subpath == "upload":
        if not user_id:
            return json_response({"detail": "Could not validate credentials"}, 401)
        return await upload_photos(env, request, user_id)

    if len(parts) == 2 and parts[1] == "status" and method == "GET":
        return await photo_status(env, parts[0])

    if len(parts) == 2 and parts[1] == "tags" and method == "GET":
        return await get_tags(env, parts[0])

    if len(parts) == 3 and parts[1] == "tags" and method == "PATCH":
        if not user_id:
            return json_response({"detail": "Could not validate credentials"}, 401)
        return await correct_tag(env, parts[0], parts[2], request, user_id)

    if len(parts) == 2 and parts[1] == "tags" and method == "POST":
        if not user_id:
            return json_response({"detail": "Could not validate credentials"}, 401)
        return await add_manual_tag(env, parts[0], request, user_id)

    return json_response({"detail": "Not found"}, 404)


async def upload_photos(env, request, current_user_id: str):
    _, files = await parse_multipart(request)
    images = list(files.values())
    if not images and "images" in files:
        images = [files["images"]]
    if not images:
        return json_response({"detail": "At least one image is required"}, 400)

    db = create_db(env.DATABASE_URL)
    upload_ids: list[str] = []
    try:
        for img in images:
            photo_id = str(uuid.uuid4())
            ext = img.name.split(".")[-1] if "." in img.name else "jpg"
            now = datetime.now(timezone.utc)
            storage_key = (
                f"uploads/{now.year}/{now.month:02d}/{now.day:02d}/{photo_id}.{ext}"
            )
            await upload_image(env, img.data, storage_key, img.content_type)
            db.execute(
                """
                INSERT INTO photos (id, owner_id, storage_url, status)
                VALUES (%s::uuid, %s::uuid, %s, 'pending')
                """,
                (photo_id, current_user_id, storage_key),
            )
            upload_ids.append(photo_id)

        for photo_id in upload_ids:
            row = db.fetchone("SELECT storage_url FROM photos WHERE id = %s::uuid", (photo_id,))
            storage_url = get_image_url(env, row["storage_url"], True)
            await enqueue_photo(env, photo_id, storage_url)

        return json_response({"upload_ids": upload_ids, "status": "pending"}, 202)
    finally:
        db.close()


async def photo_status(env, photo_id: str):
    db = create_db(env.DATABASE_URL)
    try:
        row = db.fetchone("SELECT id, status FROM photos WHERE id = %s::uuid", (photo_id,))
        if not row:
            return json_response({"detail": "Photo not found"}, 404)
        return json_response({"photo_id": str(row["id"]), "status": row["status"]})
    finally:
        db.close()


async def get_tags(env, photo_id: str):
    db = create_db(env.DATABASE_URL)
    try:
        photo = db.fetchone("SELECT id FROM photos WHERE id = %s::uuid", (photo_id,))
        if not photo:
            return json_response({"detail": "Photo not found"}, 404)

        tags = db.fetchall(
            """
            SELECT pt.id, pt.user_id, u.username, pt.bbox_x, pt.bbox_y,
                   pt.bbox_width, pt.bbox_height, pt.confidence, pt.source
            FROM photo_tags pt
            JOIN users u ON pt.user_id = u.id
            WHERE pt.photo_id = %s::uuid
            """,
            (photo_id,),
        )
        return json_response(
            {
                "photo_id": photo_id,
                "tags": [
                    {
                        "tag_id": str(tag["id"]),
                        "user_id": str(tag["user_id"]),
                        "username": tag["username"],
                        "bbox": {
                            "x": tag["bbox_x"],
                            "y": tag["bbox_y"],
                            "width": tag["bbox_width"],
                            "height": tag["bbox_height"],
                        },
                        "confidence": tag["confidence"],
                        "source": tag["source"],
                    }
                    for tag in tags
                ],
            }
        )
    finally:
        db.close()


async def correct_tag(env, photo_id: str, tag_id: str, request, current_user_id: str):
    payload = await parse_json(request)
    db = create_db(env.DATABASE_URL)
    try:
        tag = db.fetchone("SELECT id, photo_id, user_id FROM photo_tags WHERE id = %s::uuid", (tag_id,))
        if not tag or str(tag["photo_id"]) != photo_id:
            return json_response({"detail": "Tag not found on this photo"}, 404)

        action = payload.get("action")
        if action == "remove":
            db.execute("DELETE FROM photo_tags WHERE id = %s::uuid", (tag_id,))
            return json_response({"updated": True})

        if action != "reassign":
            return json_response({"detail": "Action must be 'reassign' or 'remove'"}, 400)

        new_user_id = payload.get("new_user_id")
        if not new_user_id:
            return json_response({"detail": "new_user_id is required for reassign action"}, 400)

        user = db.fetchone("SELECT id FROM users WHERE id = %s::uuid", (new_user_id,))
        if not user:
            return json_response({"detail": "New user not found"}, 404)

        db.execute(
            """
            UPDATE photo_tags
            SET user_id = %s::uuid, source = 'manual', confidence = NULL
            WHERE id = %s::uuid
            """,
            (new_user_id, tag_id),
        )

        emb = [random.gauss(0, 1) for _ in range(512)]
        norm = math.sqrt(sum(x * x for x in emb)) or 1.0
        crop_embedding = [x / norm for x in emb]

        db.execute(
            """
            INSERT INTO face_embeddings (user_id, embedding, source, source_photo_id)
            VALUES (%s::uuid, %s::vector, 'correction', %s::uuid)
            """,
            (new_user_id, embedding_literal(crop_embedding), photo_id),
        )
        db.execute(
            """
            INSERT INTO notifications (user_id, type, photo_id, actor_user_id, is_read)
            VALUES (%s::uuid, 'tagged_in_photo', %s::uuid, %s::uuid, false)
            """,
            (new_user_id, photo_id, current_user_id),
        )
        return json_response({"updated": True})
    finally:
        db.close()


async def add_manual_tag(env, photo_id: str, request, current_user_id: str):
    payload = await parse_json(request)
    target_user_id = payload.get("user_id")
    if not target_user_id:
        return json_response({"detail": "user_id is required"}, 400)

    bbox = payload.get("bbox") or {}
    db = create_db(env.DATABASE_URL)
    try:
        user = db.fetchone("SELECT id FROM users WHERE id = %s::uuid", (target_user_id,))
        if not user:
            return json_response({"detail": "Target user not found"}, 404)

        tag = db.fetchone(
            """
            INSERT INTO photo_tags (
                photo_id, user_id, bbox_x, bbox_y, bbox_width, bbox_height,
                confidence, source
            )
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, NULL, 'manual')
            RETURNING id
            """,
            (
                photo_id,
                target_user_id,
                bbox.get("x"),
                bbox.get("y"),
                bbox.get("width"),
                bbox.get("height"),
            ),
        )
        db.execute(
            """
            INSERT INTO notifications (user_id, type, photo_id, actor_user_id, is_read)
            VALUES (%s::uuid, 'tagged_in_photo', %s::uuid, %s::uuid, false)
            """,
            (target_user_id, photo_id, current_user_id),
        )
        return json_response({"tag_id": str(tag["id"]), "created": True})
    finally:
        db.close()
