import uuid
import re
import jwt
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from .database import get_db
from .models import User, FaceEmbedding, UnknownFace, PhotoTag, Notification, Photo
from .storage import upload_image, get_image_url
from .config import (
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_SECRET_KEY,
    SUPABASE_JWT_SECRET,
    SUPABASE_JWKS_URL,
    INFERENCE_SERVER_URL,
    INFERENCE_TIMEOUT_SECONDS,
    SIMILARITY_THRESHOLD,
    inference_request_headers,
    inference_runsync_url,
)
from .profile_utils import (
    user_profile_dict,
    generate_username,
    compute_zodiac,
    parse_birthday,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Profile"])
security = HTTPBearer(auto_error=False)

_jwks_client = None


def decode_supabase_token(token: str) -> dict:
    issuer = f"{SUPABASE_URL.rstrip('/')}/auth/v1" if SUPABASE_URL else None
    decode_opts = {"verify_aud": True}
    if issuer:
        decode_opts["verify_iss"] = True

    try:
        if SUPABASE_JWKS_URL:
            global _jwks_client
            if _jwks_client is None:
                from jwt import PyJWKClient
                _jwks_client = PyJWKClient(SUPABASE_JWKS_URL, cache_keys=True)
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256", "EdDSA"],
                audience="authenticated",
                issuer=issuer,
                options=decode_opts,
            )

        if SUPABASE_JWT_SECRET:
            return jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=issuer,
                options=decode_opts,
            )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase auth is not configured (set SUPABASE_JWKS_URL or SUPABASE_JWT_SECRET)",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Supabase token",
        ) from exc


def get_auth_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_supabase_token(credentials.credentials)


def provision_user(db: Session, payload: dict) -> User:
    """Find or create the app user row for a Supabase auth identity."""
    auth_user_id = uuid.UUID(payload["sub"])
    user = db.execute(
        select(User).where(User.auth_user_id == auth_user_id)
    ).scalars().first()

    email = payload.get("email")
    meta = payload.get("user_metadata") or {}
    display_name = (meta.get("display_name") or meta.get("full_name") or "").strip() or None
    preferred_username = (meta.get("username") or "").strip() or None

    if user:
        if email and not user.email:
            user.email = email
        if display_name and not user.display_name:
            user.display_name = display_name
        user.is_verified = True
        return user

    base_username = preferred_username or (email.split("@")[0] if email else f"user{str(auth_user_id)[:8]}")
    username = generate_username(db, base_username)

    user = User(
        auth_user_id=auth_user_id,
        email=email,
        username=username,
        display_name=display_name or username.replace("_", " ").title(),
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def get_current_user(
    payload: dict = Depends(get_auth_payload),
    db: Session = Depends(get_db),
) -> User:
    user = provision_user(db, payload)
    db.commit()
    db.refresh(user)
    return user


def get_current_user_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    return user.id


def user_has_face_enrollment(db: Session, user_id: uuid.UUID) -> bool:
    return db.execute(
        select(FaceEmbedding.id).where(
            FaceEmbedding.user_id == user_id,
            FaceEmbedding.source == "enrollment",
        ).limit(1)
    ).first() is not None


@router.get("/config")
async def auth_config():
    """Public Supabase client config for the frontend (anon key only)."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not configured",
        )
    return {
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": SUPABASE_ANON_KEY,
        "email_confirmation_required": False,
    }


@router.post("/register")
async def register(payload: dict = Body(...)):
    """
    Create a Supabase user without sending a confirmation email.

    Uses the admin API with email_confirm=true so signup is instant and avoids
    Supabase's built-in SMTP rate limits.
    """
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Registration is not configured (set SUPABASE_URL and SUPABASE_SECRET_KEY)",
        )

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    display_name = (payload.get("display_name") or "").strip()
    username = (payload.get("username") or "").strip().lower()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not display_name or len(display_name) > 100:
        raise HTTPException(status_code=400, detail="display_name must be 1–100 characters")
    if not re.fullmatch(r"[a-z0-9_]{3,30}", username):
        raise HTTPException(
            status_code=400,
            detail="username must be 3–30 chars: letters, numbers, underscore",
        )

    admin_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/admin/users"
    headers = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {
            "display_name": display_name,
            "username": username,
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(admin_url, headers=headers, json=body, timeout=15.0)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not reach Supabase Auth: {exc}",
        ) from exc

    if resp.status_code >= 400:
        try:
            err = resp.json()
            detail = err.get("msg") or err.get("message") or err.get("error_description") or resp.text
        except ValueError:
            detail = resp.text or "Registration failed"
        raise HTTPException(status_code=400, detail=detail)

    return {"created": True, "email": email}


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    face_enrolled = user_has_face_enrollment(db, user.id)
    return user_profile_dict(user, face_enrolled=face_enrolled)


@router.patch("/me")
async def update_me(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if "display_name" in payload:
        name = (payload.get("display_name") or "").strip()
        if not name or len(name) > 100:
            raise HTTPException(status_code=400, detail="display_name must be 1–100 characters")
        user.display_name = name

    if "username" in payload:
        uname = (payload.get("username") or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{3,30}", uname):
            raise HTTPException(
                status_code=400,
                detail="username must be 3–30 chars: letters, numbers, underscore",
            )
        taken = db.execute(
            select(User.id).where(User.username == uname, User.id != user.id)
        ).first()
        if taken:
            raise HTTPException(status_code=400, detail="username already taken")
        user.username = uname

    if "bio" in payload:
        bio = payload.get("bio")
        user.bio = (bio or "").strip()[:500] or None

    if "birthday" in payload:
        bday_raw = payload.get("birthday")
        if bday_raw in (None, ""):
            user.birthday = None
            user.zodiac_sign = None
        else:
            try:
                bday = parse_birthday(bday_raw)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="birthday must be YYYY-MM-DD") from exc
            if bday > datetime.now(timezone.utc).date():
                raise HTTPException(status_code=400, detail="birthday cannot be in the future")
            user.birthday = bday
            user.zodiac_sign = compute_zodiac(bday)

    if "mobile_number" in payload:
        mobile = (payload.get("mobile_number") or "").strip() or None
        if mobile:
            taken = db.execute(
                select(User.id).where(User.mobile_number == mobile, User.id != user.id)
            ).first()
            if taken:
                raise HTTPException(status_code=400, detail="mobile number already in use")
        user.mobile_number = mobile

    db.commit()
    db.refresh(user)
    return user_profile_dict(user, face_enrolled=user_has_face_enrollment(db, user.id))


@router.post("/profile-photo")
async def upload_profile_photo(
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_bytes = await image.read()
    ext = image.filename.split(".")[-1] if image.filename and "." in image.filename else "jpg"
    key = f"profiles/{user.id}.{ext}"
    upload_image(file_bytes, key, image.content_type or "image/jpeg")
    user.profile_photo_key = key
    db.commit()
    db.refresh(user)
    return user_profile_dict(user, face_enrolled=user_has_face_enrollment(db, user.id))


@router.post("/enroll-face")
async def enroll_face(
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = user.id
    file_bytes = await image.read()

    ext = image.filename.split(".")[-1] if image.filename and "." in image.filename else "jpg"
    filename = f"enrollments/{user_id}.{ext}"

    upload_image(file_bytes, filename, image.content_type or "image/jpeg")
    storage_url = get_image_url(filename, internal=True)

    async with httpx.AsyncClient() as client:
        predict_payload = {
            "input": {
                "images": [{"image_id": str(user_id), "url": storage_url}]
            }
        }
        try:
            resp = await client.post(
                inference_runsync_url(INFERENCE_TIMEOUT_SECONDS),
                json=predict_payload,
                headers=inference_request_headers(),
                timeout=INFERENCE_TIMEOUT_SECONDS + 30,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Inference service error: {resp.text}")

            job_result = resp.json()
            output = job_result.get("output", {})
            if job_result.get("error") or output.get("error"):
                raise HTTPException(
                    status_code=500,
                    detail=output.get("error") or job_result.get("error"),
                )

            results = output.get("results", [])
            if not results or not results[0].get("faces"):
                raise HTTPException(
                    status_code=400,
                    detail="No face detected in the enrollment image. Please try again with a clear photo of your face.",
                )

            real_embedding = results[0]["faces"][0]["embedding"]

        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Could not reach inference service: {str(exc)}",
            ) from exc

    face_emb = FaceEmbedding(
        user_id=user_id,
        embedding=real_embedding,
        source="enrollment",
        source_photo_id=None,
    )
    db.add(face_emb)
    db.flush()

    claimed_photo_ids = _claim_unknown_faces(db, user_id, real_embedding)

    db.commit()
    db.refresh(face_emb)

    return {
        "enrolled": True,
        "embedding_id": str(face_emb.id),
        "claimed_photos": len(claimed_photo_ids),
    }


def _claim_unknown_faces(db: Session, user_id: uuid.UUID, embedding: list) -> list:
    max_distance = 1.0 - SIMILARITY_THRESHOLD

    match_query = text("""
        SELECT id, photo_id, bbox_x, bbox_y, bbox_width, bbox_height, confidence,
               (embedding <=> CAST(:emb AS vector)) AS distance
        FROM unknown_faces
        WHERE claimed_at IS NULL
          AND embedding <=> CAST(:emb AS vector) <= :max_dist
        ORDER BY distance ASC
    """)
    matches = db.execute(
        match_query,
        {"emb": str(embedding), "max_dist": max_distance},
    ).all()

    claimed_photo_ids = []
    now = datetime.now(timezone.utc)

    for m in matches:
        photo = db.get(Photo, m.photo_id)
        if not photo:
            continue

        if m.photo_id in claimed_photo_ids:
            already_claimed = True
        else:
            already_claimed = db.execute(
                select(PhotoTag.id).where(
                    PhotoTag.photo_id == m.photo_id,
                    PhotoTag.user_id == user_id,
                )
            ).first() is not None

        if not already_claimed:
            tag = PhotoTag(
                photo_id=m.photo_id,
                user_id=user_id,
                bbox_x=m.bbox_x,
                bbox_y=m.bbox_y,
                bbox_width=m.bbox_width,
                bbox_height=m.bbox_height,
                confidence=m.confidence,
                source="auto",
            )
            db.add(tag)
            db.add(Notification(
                user_id=user_id,
                type="tagged_in_photo",
                photo_id=m.photo_id,
                actor_user_id=photo.owner_id,
                is_read=False,
            ))
            claimed_photo_ids.append(m.photo_id)

        db.execute(
            text("""
                UPDATE unknown_faces
                SET claimed_at = :now, claimed_by_user_id = :uid
                WHERE id = :fid
            """),
            {"now": now, "uid": str(user_id), "fid": str(m.id)},
        )

    if claimed_photo_ids:
        print(f"Enrollment for user {user_id} retroactively claimed "
              f"{len(claimed_photo_ids)} photo(s) from unknown faces.")

    return claimed_photo_ids
