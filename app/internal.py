import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import SIMILARITY_THRESHOLD
from .database import SessionLocal
from .models import Notification, Photo, PhotoTag, UnknownFace

logger = logging.getLogger("tagr-internal")

router = APIRouter(prefix="/internal", tags=["Internal Callbacks"])


def _mark_photos_failed(db: Session, photo_ids: list[str]) -> None:
    if not photo_ids:
        return
    ids = [uuid.UUID(pid) for pid in photo_ids]
    db.query(Photo).filter(Photo.id.in_(ids)).update({"status": "failed"}, synchronize_session=False)


def _process_inference_results(db: Session, batch_id: str | None, results: list) -> None:
    for item in results:
        photo_id_str = item.get("photo_id")
        if not photo_id_str:
            continue

        photo_id = uuid.UUID(photo_id_str)
        photo = db.get(Photo, photo_id)
        if not photo:
            logger.warning("Photo %s not found in database", photo_id)
            continue

        faces = item.get("faces", [])

        for face in faces:
            bbox = face.get("bbox", {})
            embedding = face.get("embedding", [])
            confidence = face.get("confidence", 1.0)

            if not embedding or len(embedding) != 512:
                continue

            max_distance = 1.0 - SIMILARITY_THRESHOLD
            match_query = text("""
                SELECT user_id, (embedding <=> CAST(:emb AS vector)) as distance
                FROM face_embeddings
                WHERE embedding <=> CAST(:emb AS vector) <= :max_dist
                ORDER BY distance ASC
                LIMIT 1
            """)
            match_result = db.execute(
                match_query,
                {"emb": str(embedding), "max_dist": max_distance},
            ).first()

            if match_result:
                matched_user_id = match_result.user_id
                logger.info(
                    "Matched face in photo %s to user %s (distance: %.4f)",
                    photo_id,
                    matched_user_id,
                    match_result.distance,
                )
                tag = PhotoTag(
                    photo_id=photo_id,
                    user_id=matched_user_id,
                    bbox_x=bbox.get("xmin"),
                    bbox_y=bbox.get("ymin"),
                    bbox_width=bbox.get("xmax", 0) - bbox.get("xmin", 0)
                    if "xmax" in bbox and "xmin" in bbox
                    else 0.1,
                    bbox_height=bbox.get("ymax", 0) - bbox.get("ymin", 0)
                    if "ymax" in bbox and "ymin" in bbox
                    else 0.1,
                    confidence=confidence,
                    source="auto",
                )
                db.add(tag)
                db.add(
                    Notification(
                        user_id=matched_user_id,
                        type="tagged_in_photo",
                        photo_id=photo_id,
                        actor_user_id=photo.owner_id,
                        is_read=False,
                    )
                )
            else:
                bbox_width = (
                    bbox.get("xmax", 0) - bbox.get("xmin", 0)
                    if "xmax" in bbox and "xmin" in bbox
                    else None
                )
                bbox_height = (
                    bbox.get("ymax", 0) - bbox.get("ymin", 0)
                    if "ymax" in bbox and "ymin" in bbox
                    else None
                )
                db.add(
                    UnknownFace(
                        photo_id=photo_id,
                        embedding=embedding,
                        bbox_x=bbox.get("xmin"),
                        bbox_y=bbox.get("ymin"),
                        bbox_width=bbox_width,
                        bbox_height=bbox_height,
                        confidence=confidence,
                    )
                )

        photo.status = "processed"
        photo.processed_at = datetime.now(timezone.utc)
        photo.batch_id = uuid.UUID(batch_id) if batch_id else None


def process_inference_callback(payload: dict) -> None:
    """Heavy face-matching work — runs in a background task after fast ACK."""
    results = payload.get("results", [])
    errors = payload.get("errors", [])
    batch_id = payload.get("batch_id")

    db = SessionLocal()
    try:
        logger.info(
            "Processing inference callback batch=%s results=%s errors=%s",
            batch_id,
            len(results),
            len(errors),
        )
        failed_ids = [str(item.get("photo_id")) for item in errors if item.get("photo_id")]
        _mark_photos_failed(db, failed_ids)
        _process_inference_results(db, batch_id, results)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Inference callback processing failed: %s", exc)
    finally:
        db.close()


@router.post("/inference-callback")
async def inference_callback(payload: dict, background_tasks: BackgroundTasks):
    """
    RunPod posts batch results here. Respond immediately so the worker does not
    time out; face matching and tagging run in the background.
    """
    background_tasks.add_task(process_inference_callback, payload)
    return {"acknowledged": True}
