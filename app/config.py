"""
Central configuration for the Tagr web/API service.

Every dynamic value (connection strings, service URLs, timeouts, thresholds,
credentials, feature knobs) is read from environment variables here so nothing
is hard-coded across the codebase. Import from this module rather than calling
os.getenv directly elsewhere.
"""

import os
from typing import List


def _get_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _get_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _get_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


# -------------------------------------------------------------------
# Database (Postgres / Supabase)
# -------------------------------------------------------------------
# Use the SQLAlchemy + psycopg driver form, e.g.
#   postgresql+psycopg://<user>:<pass>@<host>:5432/<db>?sslmode=require
DATABASE_URL = _get_str(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/tagr_db",
)
# Recycle/validate pooled connections (recommended for hosted DBs like Supabase).
DB_POOL_PRE_PING = _get_str("DB_POOL_PRE_PING", "true").lower() in ("1", "true", "yes")
DB_ECHO = _get_str("DB_ECHO", "false").lower() in ("1", "true", "yes")

# -------------------------------------------------------------------
# Supabase Auth
# -------------------------------------------------------------------
# Project URL and anon key (public) — used by the frontend via GET /auth/config.
SUPABASE_URL = _get_str("SUPABASE_URL", "")
SUPABASE_ANON_KEY = _get_str("SUPABASE_ANON_KEY", "")
# JWT secret from Supabase Dashboard -> Project Settings -> API -> JWT Secret.
# Used by the API to verify Supabase access tokens (HS256, aud=authenticated).
SUPABASE_JWT_SECRET = _get_str("SUPABASE_JWT_SECRET", "")

# -------------------------------------------------------------------
# Inference service
# -------------------------------------------------------------------
INFERENCE_SERVER_URL = _get_str("INFERENCE_SERVER_URL", "http://inference:8001")
# Timeout for a single synchronous enrollment inference call.
INFERENCE_TIMEOUT_SECONDS = _get_float("INFERENCE_TIMEOUT_SECONDS", 30.0)
# Timeout for a batched inference call from the batcher.
INFERENCE_BATCH_TIMEOUT_SECONDS = _get_float("INFERENCE_BATCH_TIMEOUT_SECONDS", 120.0)

# -------------------------------------------------------------------
# Batcher
# -------------------------------------------------------------------
BATCH_SIZE = _get_int("BATCH_SIZE", 10)
BATCH_TIMEOUT_MS = _get_float("BATCH_TIMEOUT_MS", 50.0)
API_CALLBACK_URL = _get_str(
    "API_CALLBACK_URL",
    "http://web:8000/api/v1/internal/inference-callback",
)

# -------------------------------------------------------------------
# Face matching
# -------------------------------------------------------------------
# Cosine similarity threshold: a face matches a user when
# (1 - cosine_distance) >= SIMILARITY_THRESHOLD. Used for both upload-time
# matching and retroactive claiming on enrollment.
SIMILARITY_THRESHOLD = _get_float("SIMILARITY_THRESHOLD", 0.35)

# -------------------------------------------------------------------
# Object storage (S3 / MinIO)
# -------------------------------------------------------------------
STORAGE_ENDPOINT = _get_str("STORAGE_ENDPOINT", "http://storage:9000")
STORAGE_PUBLIC_ENDPOINT = _get_str(
    "STORAGE_PUBLIC_ENDPOINT",
    STORAGE_ENDPOINT.replace("http://storage:", "http://localhost:"),
)
STORAGE_ACCESS_KEY = _get_str("STORAGE_ACCESS_KEY", "minioadmin")
STORAGE_SECRET_KEY = _get_str("STORAGE_SECRET_KEY", "minioadmin")
STORAGE_BUCKET = _get_str("STORAGE_BUCKET", "tagr-bucket")
STORAGE_REGION = _get_str("STORAGE_REGION", "us-east-1")
STORAGE_SIGNATURE_VERSION = _get_str("STORAGE_SIGNATURE_VERSION", "s3v4")

# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
def _get_cors_origins() -> List[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    if raw == "*" or not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


CORS_ALLOW_ORIGINS = _get_cors_origins()
