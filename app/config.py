"""
Central configuration for the Tagr web/API service.

Every dynamic value (connection strings, service URLs, timeouts, thresholds,
credentials, feature knobs) is read from environment variables here so nothing
is hard-coded across the codebase. Import from this module rather than calling
os.getenv directly elsewhere.
"""

import os
from typing import List, Optional
from urllib.parse import quote_plus


def _get_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _get_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _get_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _build_supabase_pooler_url() -> Optional[str]:
    """
    Build a Supabase Supavisor pooler connection string when pooler env vars are set.

    Dashboard: Project Settings -> Database -> Connection string -> Pooler
    - Transaction mode (port 6543): recommended for app servers; requires
      prepare_threshold=0 (set automatically via DB_PREPARE_THRESHOLD).
    - Session mode (port 5432 on pooler host): user postgres.<project_ref>
    """
    host = os.getenv("SUPABASE_POOLER_HOST", "").strip()
    project_ref = os.getenv("SUPABASE_PROJECT_REF", "").strip()
    password = os.getenv("SUPABASE_DB_PASSWORD", "").strip()
    if not (host and project_ref and password):
        return None

    port = _get_int("SUPABASE_POOLER_PORT", 6543)
    db_name = _get_str("SUPABASE_DB_NAME", "postgres")
    user = f"postgres.{project_ref}"
    safe_password = quote_plus(password)
    return (
        f"postgresql+psycopg://{user}:{safe_password}@{host}:{port}/{db_name}"
        f"?sslmode=require"
    )


def _normalize_database_url(url: str) -> str:
    url = url.strip()
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    if "supabase" in url and "sslmode=" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"
    return url


def _resolve_database_url() -> str:
    pooler_url = _build_supabase_pooler_url()
    if pooler_url:
        return pooler_url

    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit:
        return _normalize_database_url(explicit)

    return "postgresql+psycopg://postgres:postgres@db:5432/tagr_db"


def _resolve_prepare_threshold(database_url: str) -> Optional[int]:
    """
    Transaction-mode Supavisor (port 6543) does not support prepared statements.
    Disable them for psycopg when using that pooler endpoint.
    """
    pooler_port = os.getenv("SUPABASE_POOLER_PORT", "").strip()
    if pooler_port == "6543":
        return 0
    if "pooler.supabase.com" in database_url and ":6543" in database_url:
        return 0
    return None


# -------------------------------------------------------------------
# Database (Postgres / Supabase via Supavisor pooler)
# -------------------------------------------------------------------
DATABASE_URL = _resolve_database_url()
# Recycle/validate pooled connections (recommended for hosted DBs like Supabase).
DB_POOL_PRE_PING = _get_str("DB_POOL_PRE_PING", "true").lower() in ("1", "true", "yes")
DB_ECHO = _get_str("DB_ECHO", "false").lower() in ("1", "true", "yes")
# psycopg connect_arg: 0 disables prepared statements (required for transaction pooler).
DB_PREPARE_THRESHOLD: Optional[int] = _resolve_prepare_threshold(DATABASE_URL)

# -------------------------------------------------------------------
# Supabase Auth
# -------------------------------------------------------------------
# Project URL and client key (public) — used by the frontend via GET /auth/config.
SUPABASE_URL = _get_str("SUPABASE_URL", "")
# New Supabase publishable key (sb_publishable_...) or legacy anon JWT.
SUPABASE_PUBLISHABLE_KEY = _get_str("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_ANON_KEY = _get_str("SUPABASE_ANON_KEY", "") or SUPABASE_PUBLISHABLE_KEY
# Server-only secret (sb_secret_...) for Supabase admin APIs if needed later.
SUPABASE_SECRET_KEY = _get_str("SUPABASE_SECRET_KEY", "")
# JWKS endpoint for verifying Supabase access tokens (ES256/RS256).
SUPABASE_JWKS_URL = _get_str("SUPABASE_JWKS_URL", "")
# Legacy HS256 JWT secret — only used when JWKS URL is not set.
SUPABASE_JWT_SECRET = _get_str("SUPABASE_JWT_SECRET", "")

# -------------------------------------------------------------------
# Inference service (RunPod serverless by default)
# -------------------------------------------------------------------
INFERENCE_SERVER_URL = _get_str(
    "INFERENCE_SERVER_URL",
    "https://api.runpod.ai/v2/wid4pce4yufwbd",
)
# RunPod API key (Bearer token). Required when INFERENCE_SERVER_URL points at RunPod.
RUNPOD_API_KEY = _get_str("RUNPOD_API_KEY", "")
# Timeout for a single synchronous enrollment inference call.
INFERENCE_TIMEOUT_SECONDS = _get_float("INFERENCE_TIMEOUT_SECONDS", 60.0)
# Timeout for a batched inference call from the batcher (includes callback round-trip).
INFERENCE_BATCH_TIMEOUT_SECONDS = _get_float("INFERENCE_BATCH_TIMEOUT_SECONDS", 300.0)
# Smaller copy stored alongside original for RunPod (avoids Supabase transform quotas).
INFERENCE_IMAGE_MAX_WIDTH = _get_int("INFERENCE_IMAGE_MAX_WIDTH", 1024)
INFERENCE_IMAGE_JPEG_QUALITY = _get_int("INFERENCE_IMAGE_JPEG_QUALITY", 85)


def inference_request_headers() -> dict:
    """HTTP headers for RunPod /runsync calls (Authorization when RUNPOD_API_KEY is set)."""
    headers = {"Content-Type": "application/json"}
    if RUNPOD_API_KEY:
        headers["Authorization"] = f"Bearer {RUNPOD_API_KEY}"
    return headers


def inference_runsync_url(timeout_seconds: float | None = None) -> str:
    """RunPod /runsync URL with extended wait (default API wait is only 90s)."""
    seconds = timeout_seconds if timeout_seconds is not None else INFERENCE_BATCH_TIMEOUT_SECONDS
    wait_ms = min(int(seconds * 1000), 300000)
    return f"{INFERENCE_SERVER_URL.rstrip('/')}/runsync?wait={wait_ms}"

# -------------------------------------------------------------------
# Batcher
# -------------------------------------------------------------------
BATCH_SIZE = _get_int("BATCH_SIZE", 20)
BATCH_TIMEOUT_MS = _get_float("BATCH_TIMEOUT_MS", 5000.0)
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
# Object storage (Supabase Storage S3 / MinIO / R2)
# -------------------------------------------------------------------
STORAGE_BUCKET = _get_str("STORAGE_BUCKET", "tagr-bucket")
STORAGE_REGION = _get_str("STORAGE_REGION", "ap-southeast-1")
STORAGE_SIGNATURE_VERSION = _get_str("STORAGE_SIGNATURE_VERSION", "s3v4")
STORAGE_ACCESS_KEY = _get_str("STORAGE_ACCESS_KEY", "")
STORAGE_SECRET_KEY = _get_str("STORAGE_SECRET_KEY", "")


def _resolve_storage_endpoint() -> str:
    explicit = os.getenv("STORAGE_ENDPOINT", "").strip()
    if explicit:
        return explicit
    project_ref = os.getenv("SUPABASE_PROJECT_REF", "").strip()
    if project_ref:
        return f"https://{project_ref}.storage.supabase.co/storage/v1/s3"
    return "http://storage:9000"


def _resolve_storage_public_endpoint(storage_endpoint: str) -> str:
    explicit = os.getenv("STORAGE_PUBLIC_ENDPOINT", "").strip()
    if explicit:
        return explicit
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    if supabase_url and "supabase.co" in storage_endpoint:
        return (
            f"{supabase_url.rstrip('/')}/storage/v1/object/public/{STORAGE_BUCKET}"
        )
    return storage_endpoint.replace("http://storage:", "http://localhost:")


STORAGE_ENDPOINT = _resolve_storage_endpoint()
STORAGE_PUBLIC_ENDPOINT = _resolve_storage_public_endpoint(STORAGE_ENDPOINT)
# Optional override when inference cannot reach STORAGE_PUBLIC_ENDPOINT (legacy MinIO).
STORAGE_INFERENCE_ENDPOINT = _get_str("STORAGE_INFERENCE_ENDPOINT", "")
PRESIGNED_UPLOAD_EXPIRES_SECONDS = int(_get_float("PRESIGNED_UPLOAD_EXPIRES_SECONDS", 900))

# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
def _get_cors_origins() -> List[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    if raw == "*" or not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


CORS_ALLOW_ORIGINS = _get_cors_origins()
