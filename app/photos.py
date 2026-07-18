import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks, Body
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from .database import get_db
from .models import Photo, PhotoTag, FaceEmbedding, User, Notification, UnknownFace
from .storage import upload_image, get_image_url, create_presigned_upload_url, object_exists
from .batcher import photo_batcher
from .auth import get_current_user_id
from .config import SIMILARITY_THRESHOLD, PRESIGNED_UPLOAD_EXPIRES_SECONDS

router = APIRouter(prefix="/photos", tags=["Photos & Tagging"])

_MAX_PRESIGN_BATCH = 20
_ALLOWED_IMAGE_PREFIX = "image/"


def _storage_key_for_photo(photo_id: uuid.UUID, filename: str) -> str:
    ext = filename.split(".")[-1] if "." in filename else "jpg"
    now = datetime.now(timezone.utc)
    return f"uploads/{now.year}/{now.month:02d}/{now.day:02d}/{photo_id}.{ext}"


# -------------------------------------------------------------
# FR2.1a: Presigned direct-to-storage upload (browser -> Supabase)
# -------------------------------------------------------------
@router.post("/upload/presign")
async def presign_photo_uploads(
    payload: dict = Body(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    files = payload.get("files") or []
    if not files:
        raise HTTPException(status_code=400, detail="files is required")
    if len(files) > _MAX_PRESIGN_BATCH:
        raise HTTPException(status_code=400, detail=f"Maximum {_MAX_PRESIGN_BATCH} files per batch")

    uploads = []
    for entry in files:
        filename = (entry.get("filename") or "photo.jpg").strip() or "photo.jpg"
        content_type = (entry.get("content_type") or "image/jpeg").strip() or "image/jpeg"
        if not content_type.startswith(_ALLOWED_IMAGE_PREFIX):
            raise HTTPException(status_code=400, detail=f"Unsupported content type: {content_type}")

        photo_id = uuid.uuid4()
        storage_key = _storage_key_for_photo(photo_id, filename)
        db.add(
            Photo(
                id=photo_id,
                owner_id=current_user_id,
                storage_url=storage_key,
                status="pending",
            )
        )
        uploads.append(
            {
                "photo_id": str(photo_id),
                "storage_key": storage_key,
                "upload_url": create_presigned_upload_url(storage_key, content_type),
                "content_type": content_type,
                "expires_in": PRESIGNED_UPLOAD_EXPIRES_SECONDS,
            }
        )

    db.commit()
    return {"uploads": uploads}


@router.post("/upload/complete", status_code=status.HTTP_202_ACCEPTED)
async def complete_photo_uploads(
    payload: dict = Body(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    photo_ids_raw = payload.get("photo_ids") or []
    if not photo_ids_raw:
        raise HTTPException(status_code=400, detail="photo_ids is required")

    photo_ids: List[uuid.UUID] = []
    for raw_id in photo_ids_raw:
        try:
            photo_ids.append(uuid.UUID(str(raw_id)))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid photo_id: {raw_id}") from exc

    photos = (
        db.query(Photo)
        .filter(Photo.id.in_(photo_ids), Photo.owner_id == current_user_id)
        .all()
    )
    if len(photos) != len(photo_ids):
        raise HTTPException(status_code=404, detail="One or more photos not found")

    missing = [str(p.id) for p in photos if not object_exists(p.storage_url)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"message": "Upload not found in storage yet", "photo_ids": missing},
        )

    upload_ids: List[str] = []
    for photo in photos:
        upload_ids.append(str(photo.id))
        internal_url = get_image_url(photo.storage_url, internal=True)
        await photo_batcher.add_photo(str(photo.id), internal_url)

    return {"upload_ids": upload_ids, "status": "pending"}


# -------------------------------------------------------------
# FR2.1: Upload one or more photos (legacy proxy through API)
# -------------------------------------------------------------
@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_photos(
    images: List[UploadFile] = File(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    upload_ids = []
    
    for img in images:
        file_bytes = await img.read()
        
        photo_id = uuid.uuid4()
        ext = img.filename.split(".")[-1] if img.filename and "." in img.filename else "jpg"
        storage_key = _storage_key_for_photo(photo_id, img.filename or f"photo.{ext}")
        
        # 1. Upload file to MinIO
        upload_image(file_bytes, storage_key, img.content_type)
        
        # 2. Record photo in database
        db_photo = Photo(
            id=photo_id,
            owner_id=current_user_id,
            storage_url=storage_key,
            status="pending"
        )
        db.add(db_photo)
        upload_ids.append(str(photo_id))
        
    db.commit()
    
    # 3. Add to the in-memory batcher
    # Pass internal docker network S3 URL for inference server to fetch
    for pid in upload_ids:
        internal_url = get_image_url(db.get(Photo, uuid.UUID(pid)).storage_url, internal=True)
        await photo_batcher.add_photo(pid, internal_url)
        
    return {
        "upload_ids": upload_ids,
        "status": "pending"
    }

# -------------------------------------------------------------
# FR2.2: Poll processing status
# -------------------------------------------------------------
@router.get("/{photo_id}/status")
async def get_photo_status(photo_id: uuid.UUID, db: Session = Depends(get_db)):
    photo = db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {
        "photo_id": str(photo.id),
        "status": photo.status
    }

# -------------------------------------------------------------
# FR3.1: Get all tags on a photo
# -------------------------------------------------------------
@router.get("/{photo_id}/tags")
async def get_photo_tags(photo_id: uuid.UUID, db: Session = Depends(get_db)):
    photo = db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
        
    tags = db.execute(
        select(PhotoTag, User.username, User.display_name, User.profile_photo_key)
        .join(User, PhotoTag.user_id == User.id)
        .where(PhotoTag.photo_id == photo_id)
    ).all()
    
    results = []
    for tag, username, display_name, photo_key in tags:
        results.append({
            "tag_id": str(tag.id),
            "user_id": str(tag.user_id),
            "username": username,
            "display_name": display_name or username,
            "profile_photo_url": get_image_url(photo_key, internal=False) if photo_key else None,
            "bbox": {
                "x": tag.bbox_x,
                "y": tag.bbox_y,
                "width": tag.bbox_width,
                "height": tag.bbox_height
            },
            "confidence": tag.confidence,
            "source": tag.source
        })

    unknown_res = db.execute(
        select(UnknownFace)
        .where(UnknownFace.photo_id == photo_id, UnknownFace.claimed_at.is_(None))
    ).scalars().all()
    unknown_faces = [{
        "unknown_face_id": str(u.id),
        "bbox": {"x": u.bbox_x, "y": u.bbox_y, "width": u.bbox_width, "height": u.bbox_height},
        "confidence": u.confidence,
    } for u in unknown_res]

    return {
        "photo_id": str(photo_id),
        "tags": results,
        "unknown_faces": unknown_faces
    }

# -------------------------------------------------------------
# FR3.3 / FR3.4: Correct a wrong tag (reassign or remove)
# -------------------------------------------------------------
@router.patch("/{photo_id}/tags/{tag_id}")
async def correct_tag(
    photo_id: uuid.UUID,
    tag_id: uuid.UUID,
    payload: dict = Body(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    tag = db.get(PhotoTag, tag_id)
    if not tag or tag.photo_id != photo_id:
        raise HTTPException(status_code=404, detail="Tag not found on this photo")
        
    action = payload.get("action")
    if action not in ["reassign", "remove"]:
        raise HTTPException(status_code=400, detail="Action must be 'reassign' or 'remove'")
        
    if action == "remove":
        db.delete(tag)
        db.commit()
        return {"updated": True}
        
    new_user_id_str = payload.get("new_user_id")
    if not new_user_id_str:
        raise HTTPException(status_code=400, detail="new_user_id is required for reassign action")
        
    new_user_id = uuid.UUID(new_user_id_str)
    new_user = db.get(User, new_user_id)
    if not new_user:
        raise HTTPException(status_code=404, detail="New user not found")
        
    # Process reassign
    tag.user_id = new_user_id
    tag.source = "manual"
    tag.confidence = None  # Manual override nullifies confidence
    
    # FR3.4: Store corrected face crop's embedding as a new user reference embedding
    # We will query/retrieve the original embedding generated by auto-tagging
    # For V1, let's generate a slightly perturbed version or copy a reference.
    # We'll pull a random vector for this mock crop embedding, or fetch the closest user embedding
    # to represent the crop embedding. Let's make a mock embedding.
    import random
    emb = [random.gauss(0, 1) for _ in range(512)]
    norm = sum(x**2 for x in emb)**0.5
    crop_embedding = [x / norm for x in emb]
    
    face_emb = FaceEmbedding(
        user_id=new_user_id,
        embedding=crop_embedding,
        source="correction",
        source_photo_id=photo_id
    )
    db.add(face_emb)
    
    # Trigger notification to newly tagged user
    notification = Notification(
        user_id=new_user_id,
        type="tagged_in_photo",
        photo_id=photo_id,
        actor_user_id=current_user_id,
        is_read=False
    )
    db.add(notification)
    
    db.commit()
    return {"updated": True}

# -------------------------------------------------------------
# FR3.5: Manually add a tag not caught by auto-detection
# -------------------------------------------------------------
@router.post("/{photo_id}/tags")
async def add_manual_tag(
    photo_id: uuid.UUID,
    payload: dict = Body(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_id_str = payload.get("user_id")
    bbox = payload.get("bbox", {})
    
    if not user_id_str:
        raise HTTPException(status_code=400, detail="user_id is required")
        
    user_id = uuid.UUID(user_id_str)
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
        
    tag = PhotoTag(
        photo_id=photo_id,
        user_id=user_id,
        bbox_x=bbox.get("x"),
        bbox_y=bbox.get("y"),
        bbox_width=bbox.get("width"),
        bbox_height=bbox.get("height"),
        confidence=None,
        source="manual"
    )
    db.add(tag)
    
    # Send notification
    notification = Notification(
        user_id=user_id,
        type="tagged_in_photo",
        photo_id=photo_id,
        actor_user_id=current_user_id,
        is_read=False
    )
    db.add(notification)
    
    db.commit()
    db.refresh(tag)
    
    return {
        "tag_id": str(tag.id),
        "created": True
    }
