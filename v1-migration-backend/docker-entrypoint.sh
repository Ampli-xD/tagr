#!/bin/sh
set -e

cat > .dev.vars <<EOF
DATABASE_URL=${DATABASE_URL}
JWT_SECRET=${JWT_SECRET:-tagr-super-secret-key-12345}
STORAGE_ENDPOINT=${STORAGE_ENDPOINT:-http://storage:9000}
STORAGE_PUBLIC_ENDPOINT=${STORAGE_PUBLIC_ENDPOINT:-http://localhost:9000}
STORAGE_ACCESS_KEY=${STORAGE_ACCESS_KEY:-minioadmin}
STORAGE_SECRET_KEY=${STORAGE_SECRET_KEY:-minioadmin}
STORAGE_BUCKET=${STORAGE_BUCKET:-tagr-bucket}
INFERENCE_URL=${INFERENCE_URL:-http://inference:8001}
API_CALLBACK_URL=${API_CALLBACK_URL:-http://worker:8787/api/v1/internal/inference-callback}
EOF

exec uv run python src/local_server.py
