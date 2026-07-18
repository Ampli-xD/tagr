# Tagr — Cloudflare Worker API (Python)

Python Cloudflare Worker backend using **pywrangler** and **pg8000**.

## Docker Compose (from repo root)

```bash
cp .env.example .env
docker compose up -d --build
```

| Service | URL |
|---------|-----|
| API + UI | http://localhost:8787 |
| Health | http://localhost:8787/api/v1/health |
| MinIO | http://localhost:9001 |
| Inference | http://localhost:8001 |

## Local dev (host)

```bash
docker compose up -d db storage inference
cd v1-migration-backend
cp .dev.vars.example .dev.vars
uv sync
uv run python src/local_server.py
```

> **Note:** `pywrangler dev` runs Python inside Pyodide, which cannot open TCP sockets to Postgres. Use `local_server.py` for local/Docker development. Use `pywrangler deploy` for Cloudflare (with Hyperdrive or another DB bridge).

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Postgres connection string |
| `JWT_SECRET` | HS256 signing secret |
| `STORAGE_ENDPOINT` | MinIO internal URL (`http://storage:9000` in Docker) |
| `STORAGE_PUBLIC_ENDPOINT` | Browser-facing MinIO URL |
| `STORAGE_ACCESS_KEY` | S3 access key |
| `STORAGE_SECRET_KEY` | S3 secret key |
| `STORAGE_BUCKET` | Bucket name |
| `INFERENCE_URL` | RunPod-compatible inference service URL |
| `API_CALLBACK_URL` | Worker callback for inference results |
| `BATCH_SIZE` | Photos per inference batch (wrangler var) |
| `BATCH_TIMEOUT_MS` | Batch flush timeout ms (wrangler var) |
| `SIMILARITY_THRESHOLD` | Face match threshold (wrangler var) |

## Deploy to Cloudflare

Configure production secrets in the Cloudflare dashboard, then:

```bash
uv run pywrangler deploy
```
