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

# Initialize the main App
app = FastAPI(title="Tagr Gateways")


@app.on_event("startup")
def ensure_schema():
    try:
        with engine.begin() as conn:
            conn.execute(text(UNKNOWN_FACES_DDL))
    except Exception as exc:
        print(f"WARNING: unknown_faces schema bootstrap failed: {exc}")

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


# Mount API
app.mount("/api/v1", api_v1)

# Check if we should serve static frontend files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Mount frontend client at root
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
