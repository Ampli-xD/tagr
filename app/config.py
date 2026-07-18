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
# URL reachable from the inference container when fetching images (may differ from
# STORAGE_ENDPOINT when the web service uses host networking).
STORAGE_INFERENCE_ENDPOINT = _get_str("STORAGE_INFERENCE_ENDPOINT", "")
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
