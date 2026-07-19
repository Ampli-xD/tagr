import uuid
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import get_db
from .models import Photo, PhotoTag, FaceEmbedding, Notification, User, UnknownFace
from .config import SIMILARITY_THRESHOLD

router = APIRouter(prefix="/internal", tags=["Internal Callbacks"])

@router.post("/inference-callback")
async def inference_callback(payload: dict, db: Session = Depends(get_db)):
    """
    Callback endpoint hit by the inference layer once a batch finishes processing.
    Matches embeddings to users, writes tags, creates notifications, and updates photo statuses.
    """
    results = payload.get("results", [])
    batch_id = payload.get("batch_id")
    
    print(f"Received inference callback for batch: {batch_id}. Images count: {len(results)}")
    total_embeddings = db.execute(text("SELECT COUNT(*) FROM face_embeddings")).scalar()
    print(f"DEBUG: total face_embeddings visible to this session: {total_embeddings}")
    
    for item in results:
        photo_id_str = item.get("photo_id")
        if not photo_id_str:
            continue
            
        photo_id = uuid.UUID(photo_id_str)
        photo = db.get(Photo, photo_id)
        if not photo:
            print(f"Warning: Photo {photo_id} not found in database.")
            continue
            
        faces = item.get("faces", [])
        
        for face in faces:
            bbox = face.get("bbox", {})
            embedding = face.get("embedding", [])
            confidence = face.get("confidence", 1.0)
            
            if not embedding or len(embedding) != 512:
                continue
                
            # Perform Cosine Distance search in Postgres using pgvector
            # We want: 1 - CosineDistance >= SIMILARITY_THRESHOLD
            # Distance <=> is Cosine Distance. So CosineDistance <= 1 - SIMILARITY_THRESHOLD
            max_distance = 1.0 - SIMILARITY_THRESHOLD
            
            # Find the closest matching face embedding in the database
            match_query = text("""
                SELECT user_id, (embedding <=> CAST(:emb AS vector)) as distance
                FROM face_embeddings
                WHERE embedding <=> CAST(:emb AS vector) <= :max_dist
                ORDER BY distance ASC
                LIMIT 1
            """)
            
            match_result = db.execute(
                match_query, 
                {"emb": str(embedding), "max_dist": max_distance}
            ).first()
            
            if match_result:
                matched_user_id = match_result.user_id
                print(f"Matched face in photo {photo_id} to user {matched_user_id} (distance: {match_result.distance:.4f})")
                
                # Write tag
                tag = PhotoTag(
                    photo_id=photo_id,
                    user_id=matched_user_id,
                    bbox_x=bbox.get("xmin"),
                    bbox_y=bbox.get("ymin"),
                    bbox_width=bbox.get("xmax", 0) - bbox.get("xmin", 0) if "xmax" in bbox and "xmin" in bbox else 0.1,
                    bbox_height=bbox.get("ymax", 0) - bbox.get("ymin", 0) if "ymax" in bbox and "ymin" in bbox else 0.1,
                    confidence=confidence,
                    source="auto"
                )
                db.add(tag)
                
                # Trigger notification if matching user is not the owner (or even if they are, per spec)
                notification = Notification(
                    user_id=matched_user_id,
                    type="tagged_in_photo",
                    photo_id=photo_id,
                    actor_user_id=photo.owner_id,
                    is_read=False
                )
                db.add(notification)
            else:
                # No enrolled user matched this face. Instead of discarding the
                # embedding, persist it as an "unknown" face so that if the person
                # registers later they can retroactively claim every photo they
                # appear in (see enroll_face in auth.py).
                bbox_width = (
                    bbox.get("xmax", 0) - bbox.get("xmin", 0)
                    if "xmax" in bbox and "xmin" in bbox else None
                )
                bbox_height = (
                    bbox.get("ymax", 0) - bbox.get("ymin", 0)
                    if "ymax" in bbox and "ymin" in bbox else None
                )
                unknown = UnknownFace(
                    photo_id=photo_id,
                    embedding=embedding,
                    bbox_x=bbox.get("xmin"),
                    bbox_y=bbox.get("ymin"),
                    bbox_width=bbox_width,
                    bbox_height=bbox_height,
                    confidence=confidence,
                )
                db.add(unknown)

                # Log the closest miss for debugging/threshold tuning.
                debug_query = text("""
                    SELECT user_id, (embedding <=> CAST(:emb AS vector)) as distance
                    FROM face_embeddings
                    ORDER BY distance ASC
                    LIMIT 1
                """)
                closest = db.execute(debug_query, {"emb": str(embedding)}).first()
                if closest:
                    closest_sim = 1.0 - closest.distance
                    print(f"No match found for face in photo {photo_id}; stored as unknown "
                        f"(closest was user {closest.user_id}, similarity: {closest_sim:.4f})")
                else:
                    print(f"No match found for face in photo {photo_id}; stored as unknown "
                        f"(no embeddings in DB at all)")

        # Update photo status to processed
        photo.status = "processed"
        photo.processed_at = datetime.now(timezone.utc)
        photo.batch_id = uuid.UUID(batch_id) if batch_id else None
        
    db.commit()
    return {"acknowledged": True}
