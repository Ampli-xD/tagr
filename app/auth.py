import os
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from .database import get_db
from .models import User, OTPRequest, FaceEmbedding, UnknownFace, PhotoTag, Notification, Photo
from .storage import upload_image, get_image_url
from .internal import SIMILARITY_THRESHOLD

router = APIRouter(prefix="/auth", tags=["Authentication & Enrollment"])

JWT_SECRET = os.getenv("JWT_SECRET", "tagr-super-secret-key-12345")
JWT_ALGORITHM = "HS256"
security = HTTPBearer()
INFERENCE_SERVER_URL = os.getenv("INFERENCE_SERVER_URL", "http://inference:8001")

def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id_str: str = payload.get("user_id")
        if user_id_str is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return uuid.UUID(user_id_str)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

# -------------------------------------------------------------
# FR1.1: Register a new user
# -------------------------------------------------------------
@router.post("/register")
async def register(mobile_number: str = Form(...), username: str = Form(...), db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.execute(select(User).where((User.mobile_number == mobile_number) | (User.username == username))).scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or Mobile number already registered")

    # Create unverified user
    new_user = User(
        mobile_number=mobile_number,
        username=username,
        is_verified=False
    )
    db.add(new_user)
    
    # Mock OTP flow: create a dummy OTP request
    # Code is always 123456 for V1 testing simplicity
    otp_code = "123456"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    otp_req = OTPRequest(
        mobile_number=mobile_number,
        otp_code=otp_code,
        expires_at=expires_at
    )
    db.add(otp_req)
    db.commit()
    db.refresh(new_user)
    
    # Log to console per FR1.1 spec
    print(f"--- MOCK OTP --- Sent OTP {otp_code} to {mobile_number} (expires in 5 minutes)")
    
    return {
        "user_id": str(new_user.id),
        "otp_sent": True
    }

# -------------------------------------------------------------
# FR1.2 / FR1.3: Verify OTP
# -------------------------------------------------------------
@router.post("/verify-otp")
async def verify_otp(mobile_number: str = Form(...), otp: str = Form(...), db: Session = Depends(get_db)):
    # Fetch active OTP request
    otp_req = db.execute(
        select(OTPRequest)
        .where(OTPRequest.mobile_number == mobile_number)
        .order_by(OTPRequest.created_at.desc())
    ).scalars().first()

    if not otp_req or otp_req.otp_code != otp or otp_req.verified or otp_req.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid, expired or already verified OTP")

    otp_req.verified = True
    
    # Verify the user associated with this mobile number
    user = db.execute(select(User).where(User.mobile_number == mobile_number)).scalars().first()
    if user:
        user.is_verified = True
        
    db.commit()

    # Issue JWT Token
    token = create_access_token(data={"user_id": str(user.id)})
    
    return {
        "verified": True,
        "token": token
    }

# -------------------------------------------------------------
# FR1.3: Submit live face capture for embedding enrollment
# -------------------------------------------------------------
@router.post("/enroll-face")
async def enroll_face(
    user_id: uuid.UUID = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    # Read image contents
    file_bytes = await image.read()
    
    # Unique storage name for the enrollment image
    ext = image.filename.split(".")[-1] if "." in image.filename else "jpg"
    filename = f"enrollments/{user_id}.{ext}"
    
    # Upload enrollment photo to storage
    upload_image(file_bytes, filename, image.content_type)
    
    # Build internal URL for the inference service to fetch
    internal_url = f"{INFERENCE_SERVER_URL.rstrip('/')}"
    storage_url = get_image_url(filename, internal=True)
    
    # Call the inference service to extract a real face embedding
    import httpx
    async with httpx.AsyncClient() as client:
        predict_payload = {
            "input": {
                "images": [{"image_id": str(user_id), "url": storage_url}]
            }
        }
        try:
            resp = await client.post(
                f"{INFERENCE_SERVER_URL.rstrip('/')}/runsync",
                json=predict_payload,
                timeout=30.0,
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
                raise HTTPException(status_code=400, detail="No face detected in the enrollment image. Please try again with a clear photo of your face.")
            
            face = results[0]["faces"][0]
            real_embedding = face["embedding"]
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Could not reach inference service: {str(e)}")
    
    # Save the canonical reference embedding (real vector from InsightFace)
    face_emb = FaceEmbedding(
        user_id=user_id,
        embedding=real_embedding,
        source="enrollment",
        source_photo_id=None
    )
    db.add(face_emb)
    db.flush()

    # Retroactively claim any previously-unknown faces that match this newly
    # enrolled user. This lets a person who appeared in others' photos before
    # registering automatically receive all of those photos on sign-up.
    claimed_photo_ids = _claim_unknown_faces(db, user_id, real_embedding)

    db.commit()
    db.refresh(face_emb)

    return {
        "enrolled": True,
        "embedding_id": str(face_emb.id),
        "claimed_photos": len(claimed_photo_ids),
    }


def _claim_unknown_faces(db: Session, user_id: uuid.UUID, embedding: list) -> list:
    """
    Find unclaimed unknown faces within the similarity threshold of the given
    enrollment embedding, convert each into a real auto-tag for the user, notify
    them, and mark the unknown face as claimed. Returns the list of photo IDs the
    user was newly tagged in (deduplicated to one tag per photo).
    """
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

        # One tag per (photo, user): skip if already tagged (either from an
        # earlier claim in this loop or a pre-existing tag).
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

        # Mark the unknown face as claimed regardless, so it is not re-processed.
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

# -------------------------------------------------------------
# Login Endpoint
# -------------------------------------------------------------
@router.post("/login")
async def login(mobile_number: str = Form(...), otp: str = Form(...), db: Session = Depends(get_db)):
    # For V1, the login flow expects OTP code
    otp_req = db.execute(
        select(OTPRequest)
        .where(OTPRequest.mobile_number == mobile_number)
        .order_by(OTPRequest.created_at.desc())
    ).scalars().first()

    if not otp_req or otp_req.otp_code != otp or otp_req.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    user = db.execute(select(User).where(User.mobile_number == mobile_number)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found. Please register first.")

    token = create_access_token(data={"user_id": str(user.id)})
    return {
        "token": token,
        "user_id": str(user.id)
    }

# -------------------------------------------------------------
# GET Current Profile
# -------------------------------------------------------------
@router.get("/me")
async def me(user_id: uuid.UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    return {
        "user_id": str(user.id),
        "username": user.username,
        "mobile_number": user.mobile_number,
        "created_at": user.created_at
    }

# -------------------------------------------------------------
# FR1.4: Request login OTP
# -------------------------------------------------------------
@router.post("/request-login-otp")
async def request_login_otp(mobile_number: str = Form(...), db: Session = Depends(get_db)):
    # Ensure user exists and is verified
    user = db.execute(select(User).where(User.mobile_number == mobile_number)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not verified")
    # Mock OTP generation (same dummy code as registration)
    otp_code = "123456"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    otp_req = OTPRequest(
        mobile_number=mobile_number,
        otp_code=otp_code,
        expires_at=expires_at
    )
    db.add(otp_req)
    db.commit()
    print(f"--- MOCK OTP --- Sent OTP {otp_code} to {mobile_number} (expires in 5 minutes)")
    return {"otp_sent": True}
