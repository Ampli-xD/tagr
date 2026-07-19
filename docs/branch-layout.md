# Branch layout

| Branch | API hosting | Inference | Frontend |
|---|---|---|---|
| **`v1`** | Local Docker | Local `inference` container | `app/static/` same-origin — no wake screen |
| **`production`** | Render (free/starter) | RunPod GPU | Vercel — wake screen + MVP message |

## v1 (local dev)

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d web inference
```

Open `http://127.0.0.1:8787/` — API and UI on same machine. No backend wake-up flow.

## production (MVP live)

1. **API on Render** — branch `production`, see `docs/deploy-render.md` (512 MB OK; inference on RunPod).
2. **UI on Vercel** — folder `frontend/`, env:
   - `TAGR_API_URL=https://YOUR-APP.onrender.com/api/v1`
   - `TAGR_WAKE_BACKEND=true`
3. First visit shows **“Starting the server”** (free Render cold start, up to ~5 min).
4. **CORS** on Render: `CORS_ALLOW_ORIGINS=https://YOUR-APP.vercel.app`
