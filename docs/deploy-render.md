# Deploy Tagr API on Render (production branch)

Use this for the **production** backend. Inference stays on **RunPod**; Render only runs the FastAPI web service.

## RAM: is 512 MB enough?

**Yes for the API alone** on MVP traffic:

- FastAPI + SQLAlchemy + Supabase pooler fits in **512 MB** (Render free/starter).
- Face **inference** runs on RunPod, not Render.
- Avoid enabling the local `inference` Docker service on Render.

Upgrade if you see OOM kills or heavy concurrent uploads.

## Steps

1. [Render Dashboard](https://dashboard.render.com) → **New → Web Service**
2. Connect repo `DishantWDTS/tagr`, branch **`production`**
3. **Runtime**: Docker
4. **Dockerfile path**: `./Dockerfile`
5. **Health check path**: `/api/v1/health`
6. **Plan**: Free (sleeps after ~15 min idle) or Starter ($7/mo always-on)

## Environment variables (Render)

Copy from `.env.example` on `production`. Minimum:

```env
# Supabase (DB, auth, storage)
SUPABASE_URL=...
SUPABASE_PUBLISHABLE_KEY=...
SUPABASE_SECRET_KEY=...
SUPABASE_JWKS_URL=...
SUPABASE_PROJECT_REF=...
SUPABASE_DB_PASSWORD=...
SUPABASE_POOLER_HOST=...
SUPABASE_POOLER_PORT=5432

# RunPod inference
INFERENCE_SERVER_URL=https://api.runpod.ai/v2/wid4pce4yufwbd
RUNPOD_API_KEY=rpa_...
API_CALLBACK_URL=https://YOUR-RENDER-HOST.onrender.com/api/v1/internal/inference-callback

# CORS — your Vercel frontend
CORS_ALLOW_ORIGINS=https://your-app.vercel.app

BATCH_SIZE=20
```

`API_CALLBACK_URL` must be your **public Render URL** (RunPod posts results there).

## Vercel frontend

See `frontend/README.md`. Set:

```env
TAGR_API_URL=https://YOUR-RENDER-HOST.onrender.com/api/v1
TAGR_WAKE_BACKEND=true
```

The UI shows an MVP message and polls `/health` until Render finishes cold start.

## Free tier behavior

| | Free Render | Starter |
|---|---|---|
| Sleeps when idle | ~15 min | No |
| Cold start | 30s – 5 min | N/A |
| RAM | 512 MB | 512 MB+ |

Cold start is why the frontend includes the **“Starting the server”** overlay.

## v1 local dev

Branch **`v1`** uses local Docker inference — do **not** deploy `v1` to Render for production. Use `docker compose up web inference` locally.
