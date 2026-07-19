# Branch layout

| Branch | Backend inference | Frontend |
|---|---|---|
| **`v1`** | Local Docker `inference` service (CPU/GPU on your machine) | `frontend/` → optional Vercel; `app/static/` served by API in dev |
| **`production`** | RunPod serverless GPU | `frontend/` → Vercel with `TAGR_API_URL` |

## v1 (local dev)

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d web inference
```

`.env`: `INFERENCE_SERVER_URL=http://127.0.0.1:8001` (host network override).

## production (live)

- Deploy **`frontend/`** to Vercel — set `TAGR_API_URL` to your public API.
- Run API with RunPod env vars (`INFERENCE_SERVER_URL`, `RUNPOD_API_KEY`, public `API_CALLBACK_URL`).
- Set `CORS_ALLOW_ORIGINS=https://your-app.vercel.app`.
