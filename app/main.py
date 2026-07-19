import os
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from .auth import router as auth_router
from .photos import router as photos_router
from .internal import router as internal_router
from .social import router as social_router
from .database import get_db, engine
from .config import CORS_ALLOW_ORIGINS

# Idempotent bootstrap for schema additions that must land on databases whose
# volume was already initialized (the init SQL only runs on a fresh volume).
UNKNOWN_FACES_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS unknown_faces (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id           UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    embedding          VECTOR(512) NOT NULL,
    bbox_x             FLOAT,
    bbox_y             FLOAT,
    bbox_width         FLOAT,
    bbox_height        FLOAT,
    confidence         FLOAT,
    claimed_by_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    claimed_at         TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_unknown_faces_photo ON unknown_faces(photo_id);
CREATE INDEX IF NOT EXISTS idx_unknown_faces_unclaimed ON unknown_faces(claimed_at) WHERE claimed_at IS NULL;
"""

PROFILE_DDL = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_user_id UUID UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo_key TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS birthday DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS zodiac_sign VARCHAR(20);
ALTER TABLE users ALTER COLUMN mobile_number DROP NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON users(auth_user_id);
"""

# Initialize the main App
app = FastAPI(title="Tagr Gateways")


@app.on_event("startup")
def ensure_schema():
    try:
        with engine.begin() as conn:
            conn.execute(text(UNKNOWN_FACES_DDL))
            conn.execute(text(PROFILE_DDL))
    except Exception as exc:
        print(f"WARNING: unknown_faces schema bootstrap failed: {exc}")


@app.on_event("startup")
def validate_runpod_callback_url():
    from .config import API_CALLBACK_URL, INFERENCE_SERVER_URL

    if "runpod.ai" not in INFERENCE_SERVER_URL:
        return
    if any(host in API_CALLBACK_URL for host in ("127.0.0.1", "localhost", "web:8000")):
        print(
            "WARNING: API_CALLBACK_URL must be a public HTTPS URL when using RunPod. "
            "RunPod workers cannot reach localhost. See docs/cloudflare-named-tunnel.md"
        )


@app.on_event("startup")
def purge_orphan_photos():
    """Remove photo rows whose storage object no longer exists (failed CORS uploads)."""
    from .database import SessionLocal
    from .models import Photo
    from .storage import object_exists

    db = SessionLocal()
    try:
        orphans = []
        for photo in db.query(Photo).all():
            if not object_exists(photo.storage_url):
                orphans.append(photo)
        if not orphans:
            return
        for photo in orphans:
            db.delete(photo)
        db.commit()
        print(f"Purged {len(orphans)} orphan photo rows (missing storage object)")
    except Exception as exc:
        db.rollback()
        print(f"WARNING: orphan photo purge failed: {exc}")
    finally:
        db.close()


@app.on_event("startup")
async def requeue_stuck_photos():
    """On boot, re-submit pending/failed photos that still exist in storage."""
    from .database import SessionLocal
    from .models import Photo
    from .storage import inference_key_for, get_image_url, object_exists
    from .batcher import photo_batcher

    db = SessionLocal()
    try:
        stuck = db.query(Photo).filter(Photo.status.in_(["pending", "failed"])).all()
        if not stuck:
            return
        requeued = 0
        to_queue = []
        for photo in stuck:
            photo.status = "pending"
            photo.batch_id = None
            photo.processed_at = None
            to_queue.append(photo)
            requeued += 1
        db.commit()
        for photo in to_queue:
            infer_key = inference_key_for(photo.storage_url)
            if object_exists(infer_key):
                url = get_image_url(infer_key, internal=True)
            else:
                url = get_image_url(photo.storage_url, internal=True)
            await photo_batcher.add_photo(str(photo.id), url)
        print(f"Requeued {requeued} photos for inference")
    except Exception as exc:
        print(f"WARNING: photo requeue on startup failed: {exc}")
    finally:
        db.close()

# Allow CORS (origins configurable via CORS_ALLOW_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Sub-app to prefix everything under /api/v1 per specification
api_v1 = FastAPI(title="Tagr API", version="1.0")
api_v1.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1.include_router(auth_router)
api_v1.include_router(photos_router)
api_v1.include_router(internal_router)
api_v1.include_router(social_router)


@api_v1.get("/health")
async def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "tagr-api"}


@api_v1.get("/health/inference")
async def health_inference():
    """Public config check — helps verify Render env before debugging RunPod."""
    from .config import (
        API_CALLBACK_URL,
        BATCH_SIZE,
        BATCH_TIMEOUT_MS,
        INFERENCE_SERVER_URL,
        RUNPOD_API_KEY,
    )

    using_runpod = "runpod.ai" in INFERENCE_SERVER_URL
    key_set = bool(RUNPOD_API_KEY.strip())
    callback_public = API_CALLBACK_URL.startswith("https://") and not any(
        host in API_CALLBACK_URL for host in ("127.0.0.1", "localhost", "web:8000")
    )
    return {
        "inference_server_url": INFERENCE_SERVER_URL,
        "using_runpod": using_runpod,
        "runpod_api_key_set": key_set,
        "runpod_ready": (not using_runpod) or (key_set and callback_public),
        "api_callback_url": API_CALLBACK_URL,
        "callback_public_https": callback_public,
        "batch_size": BATCH_SIZE,
        "batch_timeout_ms": BATCH_TIMEOUT_MS,
    }


# Mount API
app.mount("/api/v1", api_v1)

# Check if we should serve static frontend files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Mount frontend client at root
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
