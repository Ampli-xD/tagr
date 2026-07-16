# Tagr — Cloudflare Worker API (v1-migration-backend)

TypeScript/Hono Cloudflare Worker backend. Runs locally via **Wrangler** or Docker Compose.

## Quick start (Docker Compose)

From the repository root:

```bash
cp .env.example .env
docker compose up -d --build
```

| Service   | URL |
|-----------|-----|
| API + UI  | http://localhost:8787 |
| Health    | http://localhost:8787/api/v1/health |
| MinIO     | http://localhost:9001 |
| Inference | http://localhost:8001 |

## Quick start (host Wrangler)

```bash
docker compose up -d db storage inference
cd v1-migration-backend
cp .dev.vars.example .dev.vars
npm install
npm run dev
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Postgres connection string (direct, no pooler) |
| `JWT_SECRET` | HS256 signing secret |
| `STORAGE_ENDPOINT` | MinIO/S3 internal URL (`http://storage:9000` in Docker) |
| `STORAGE_PUBLIC_ENDPOINT` | Browser-facing MinIO URL (`http://localhost:9000`) |
| `STORAGE_ACCESS_KEY` | S3 access key |
| `STORAGE_SECRET_KEY` | S3 secret key |
| `STORAGE_BUCKET` | Bucket name |
| `INFERENCE_URL` | InsightFace service URL |
| `API_CALLBACK_URL` | Worker callback for inference results |

## Deploy to Cloudflare

Configure production secrets (`DATABASE_URL`, R2 credentials, etc.) in the Cloudflare dashboard, then:

```bash
npm run deploy
```
