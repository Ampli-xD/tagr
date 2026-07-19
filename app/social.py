import uuid
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import select, text, and_, or_, delete

from .database import get_db
from .models import User, Photo, PhotoTag, Comment, Notification, FriendRequest, Friendship, FaceEmbedding, UnknownFace
from .storage import get_image_url
from .auth import get_current_user_id
from .profile_utils import profile_photo_url

router = APIRouter(tags=["Social, Gallery & Notifications"])

# -------------------------------------------------------------
# FR5: Notifications
# -------------------------------------------------------------
@router.get("/notifications")
async def get_notifications(
    unread_only: bool = Query(False),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    query = select(Notification, User.username).join(User, Notification.actor_user_id == User.id, isouter=True).where(Notification.user_id == current_user_id)
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    query = query.order_by(Notification.created_at.desc())
    results = db.execute(query).all()
    
    notifications_list = []
    for notif, actor_name in results:
        notifications_list.append({
            "notification_id": str(notif.id),
            "type": notif.type,
            "photo_id": str(notif.photo_id) if notif.photo_id else None,
            "actor_user_id": str(notif.actor_user_id) if notif.actor_user_id else None,
            "actor_username": actor_name,
            "created_at": notif.created_at,
            "read": notif.is_read
        })
        
    return {"notifications": notifications_list}

@router.patch("/notifications/{notification_id}/read")
async def read_notification(
    notification_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    notif = db.get(Notification, notification_id)
    if not notif or notif.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    notif.is_read = True
    db.commit()
    return {"updated": True}

# -------------------------------------------------------------
# FR6: Gallery & Comments
# -------------------------------------------------------------
@router.get("/users/{user_id}/gallery")
async def get_user_gallery(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # Find all photos where the user is tagged
    offset = (page - 1) * limit
    
    # Query photos matching tags
    stmt = (
        select(Photo)
        .join(PhotoTag, Photo.id == PhotoTag.photo_id)
        .where(PhotoTag.user_id == user_id)
        .order_by(Photo.uploaded_at.desc())
        .offset(offset)
        .limit(limit)
    )
    photos = db.execute(stmt).scalars().all()
    
    photos_list = []
    for p in photos:
        # Get all tags for each photo
        tags_stmt = select(PhotoTag.user_id, User.username, User.display_name, User.profile_photo_key).join(User, PhotoTag.user_id == User.id).where(PhotoTag.photo_id == p.id)
        tags_res = db.execute(tags_stmt).all()
        tagged_users = [{
            "user_id": str(t[0]),
            "username": t[1],
            "display_name": t[2] or t[1],
            "profile_photo_url": get_image_url(t[3], internal=False) if t[3] else None,
        } for t in tags_res]
        
        photos_list.append({
            "photo_id": str(p.id),
            "url": get_image_url(p.storage_url, internal=False),
            "uploaded_by": str(p.owner_id),
            "uploaded_at": p.uploaded_at,
            "tagged_users": tagged_users
        })
        
    return {"photos": photos_list}

@router.get("/photos/{photo_id}")
async def get_photo_details(
    photo_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    photo = db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
        
    # Get tags
    tags_stmt = select(PhotoTag, User.username, User.display_name, User.profile_photo_key).join(User, PhotoTag.user_id == User.id).where(PhotoTag.photo_id == photo_id)
    tags_res = db.execute(tags_stmt).all()
    tags = [{
        "tag_id": str(t[0].id),
        "user_id": str(t[0].user_id),
        "username": t[1],
        "display_name": t[2] or t[1],
        "profile_photo_url": get_image_url(t[3], internal=False) if t[3] else None,
        "bbox": {"x": t[0].bbox_x, "y": t[0].bbox_y, "width": t[0].bbox_width, "height": t[0].bbox_height},
        "confidence": t[0].confidence,
        "source": t[0].source
    } for t in tags_res]

    # Unidentified faces detected but not yet matched to a registered user.
    unknown_res = db.execute(
        select(UnknownFace)
        .where(UnknownFace.photo_id == photo_id, UnknownFace.claimed_at.is_(None))
    ).scalars().all()
    unknown_faces = [{
        "unknown_face_id": str(u.id),
        "bbox": {"x": u.bbox_x, "y": u.bbox_y, "width": u.bbox_width, "height": u.bbox_height},
        "confidence": u.confidence,
    } for u in unknown_res]

    # Get comments
    comments_stmt = select(Comment, User.username, User.display_name, User.profile_photo_key).join(User, Comment.user_id == User.id).where(Comment.photo_id == photo_id).order_by(Comment.created_at.asc())
    comments_res = db.execute(comments_stmt).all()
    comments = [{
        "comment_id": str(c[0].id),
        "user_id": str(c[0].user_id),
        "username": c[1],
        "display_name": c[2] or c[1],
        "profile_photo_url": get_image_url(c[3], internal=False) if c[3] else None,
        "text": c[0].text,
        "created_at": c[0].created_at
    } for c in comments_res]
    
    return {
        "photo_id": str(photo.id),
        "url": get_image_url(photo.storage_url, internal=False),
        "owner_id": str(photo.owner_id),
        "status": photo.status,
        "tags": tags,
        "unknown_faces": unknown_faces,
        "comments": comments
    }

@router.post("/photos/{photo_id}/comments")
async def add_comment(
    photo_id: uuid.UUID,
    payload: dict = Body(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    text_content = payload.get("text")
    if not text_content:
        raise HTTPException(status_code=400, detail="Comment text is required")
        
    photo = db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
        
    comment = Comment(
        photo_id=photo_id,
        user_id=current_user_id,
        text=text_content
    )
    db.add(comment)
    db.commit()
    return {"comment_id": str(comment.id), "created": True}

@router.get("/photos/{photo_id}/comments")
async def list_comments(photo_id: uuid.UUID, db: Session = Depends(get_db)):
    comments = db.execute(
        select(Comment, User.username)
        .join(User, Comment.user_id == User.id)
        .where(Comment.photo_id == photo_id)
        .order_by(Comment.created_at.asc())
    ).all()
    
    comments_list = [{
        "comment_id": str(c[0].id),
        "user_id": str(c[0].user_id),
        "username": c[1],
        "text": c[0].text,
        "created_at": c[0].created_at
    } for c in comments]
    
    return {"comments": comments_list}

# -------------------------------------------------------------
# FR7: Social Graph (Friends suggestions, Friend Request, Friends)
# -------------------------------------------------------------
@router.get("/friends/suggestions")
async def get_friend_suggestions(
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # Co-appearance SQL Query
    query = text("""
        SELECT pt2.user_id as suggested_id, u.username, u.display_name, u.profile_photo_key,
               COUNT(pt1.photo_id) as mutual_photos
        FROM photo_tags pt1
        JOIN photo_tags pt2 ON pt1.photo_id = pt2.photo_id AND pt1.user_id != pt2.user_id
        JOIN users u ON pt2.user_id = u.id
        WHERE pt1.user_id = :curr_id
          AND NOT EXISTS (
              SELECT 1 FROM friendships f 
              WHERE (f.user_a_id = :curr_id AND f.user_b_id = pt2.user_id) 
                 OR (f.user_b_id = :curr_id AND f.user_a_id = pt2.user_id)
          )
          AND NOT EXISTS (
              SELECT 1 FROM friend_requests fr 
              WHERE (fr.from_user_id = :curr_id AND fr.to_user_id = pt2.user_id) 
                 OR (fr.from_user_id = pt2.user_id AND fr.to_user_id = :curr_id)
          )
        GROUP BY pt2.user_id, u.username, u.display_name, u.profile_photo_key
        ORDER BY mutual_photos DESC
    """)
    
    rows = db.execute(query, {"curr_id": current_user_id}).all()
    suggestions = [{
        "user_id": str(r[0]),
        "username": r[1],
        "display_name": r[2] or r[1],
        "profile_photo_url": get_image_url(r[3], internal=False) if r[3] else None,
        "mutual_photo_count": r[4]
    } for r in rows]
    
    return {"suggestions": suggestions}

@router.post("/friends/request")
async def send_friend_request(
    payload: dict = Body(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    target_user_id_str = payload.get("target_user_id")
    if not target_user_id_str:
        raise HTTPException(status_code=400, detail="target_user_id is required")
        
    target_user_id = uuid.UUID(target_user_id_str)
    
    if current_user_id == target_user_id:
        raise HTTPException(status_code=400, detail="Cannot send friend request to yourself")
        
    # Verify target exists
    target = db.get(User, target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")
        
    # Check if already friends
    already_friends = db.execute(
        select(Friendship)
        .where(
            or_(
                and_(Friendship.user_a_id == current_user_id, Friendship.user_b_id == target_user_id),
                and_(Friendship.user_a_id == target_user_id, Friendship.user_b_id == current_user_id)
            )
        )
    ).scalars().first()
    
    if already_friends:
        raise HTTPException(status_code=400, detail="Already friends with this user")
        
    # Check if request already exists
    existing_req = db.execute(
        select(FriendRequest)
        .where(
            or_(
                and_(FriendRequest.from_user_id == current_user_id, FriendRequest.to_user_id == target_user_id),
                and_(FriendRequest.from_user_id == target_user_id, FriendRequest.to_user_id == current_user_id)
            )
        )
    ).scalars().first()
    
    if existing_req:
        return {"request_id": str(existing_req.id), "status": existing_req.status}
        
    req = FriendRequest(
        from_user_id=current_user_id,
        to_user_id=target_user_id,
        origin="explicit",
        status="pending"
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    
    return {"request_id": str(req.id), "status": "pending"}

@router.post("/friends/request/{request_id}/respond")
async def respond_friend_request(
    request_id: uuid.UUID,
    payload: dict = Body(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    action = payload.get("action")
    if action not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'reject'")
        
    req = db.get(FriendRequest, request_id)
    if not req or req.to_user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Request not found or not addressed to you")
        
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request already processed")
        
    if action == "reject":
        req.status = "rejected"
        req.responded_at = datetime.now(timezone.utc)
        db.commit()
        return {"updated": True}
        
    # Accept friend request: update request status & create friendship row
    req.status = "accepted"
    req.responded_at = datetime.now(timezone.utc)
    
    # Enforce check (user_a_id < user_b_id)
    user_a_id, user_b_id = sorted([req.from_user_id, req.to_user_id])
    
    # Ensure friendship row doesn't exist already
    friendship_exists = db.execute(
        select(Friendship).where(Friendship.user_a_id == user_a_id, Friendship.user_b_id == user_b_id)
    ).scalars().first()
    
    if not friendship_exists:
        friendship = Friendship(
            user_a_id=user_a_id,
            user_b_id=user_b_id
        )
        db.add(friendship)
        
    db.commit()
    return {"updated": True}

@router.get("/friends")
async def list_friends(
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # Find friends
    friends_stmt = text("""
        SELECT u.id, u.username, u.display_name, u.profile_photo_key, f.created_at
        FROM friendships f
        JOIN users u ON (u.id = f.user_a_id AND f.user_b_id = :curr_id)
                     OR (u.id = f.user_b_id AND f.user_a_id = :curr_id)
    """)
    
    rows = db.execute(friends_stmt, {"curr_id": current_user_id}).all()
    friends = [{
        "user_id": str(r[0]),
        "username": r[1],
        "display_name": r[2] or r[1],
        "profile_photo_url": get_image_url(r[3], internal=False) if r[3] else None,
        "since": r[4]
    } for r in rows]
    
    return {"friends": friends}

# -------------------------------------------------------------
# FR4: Embedding storage debug list
# -------------------------------------------------------------
@router.get("/users/{user_id}/embeddings")
async def get_user_embeddings(
    user_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    embs = db.execute(
        select(FaceEmbedding)
        .where(FaceEmbedding.user_id == user_id)
        .order_by(FaceEmbedding.created_at.desc())
    ).scalars().all()
    
    return {
        "user_id": str(user_id),
        "embeddings": [{
            "embedding_id": str(e.id),
            "source": e.source,
            "created_at": e.created_at
        } for e in embs]
    }
