# Tagr web frontend (Vercel)

Static SPA deployed separately from the FastAPI backend.

## Production (Vercel + Render)

1. Deploy API from **`production`** branch to [Render](https://render.com) (see `docs/deploy-render.md`).
2. Import this repo on Vercel — **Root Directory**: `frontend`, branch **`production`**.
3. Vercel environment variables:

| Variable | Example | Required |
|---|---|---|
| `TAGR_API_URL` | `https://tagr-api.onrender.com/api/v1` | Yes |
| `TAGR_WAKE_BACKEND` | `true` | Yes (free Render tier sleeps) |

4. Deploy. On first visit users see a **“Starting the server”** screen while the UI pings `/health` to wake Render (up to 5 min).

Set on the **API** (Render):

```env
CORS_ALLOW_ORIGINS=https://your-app.vercel.app
```

## Local dev (v1)

- Run API with Docker: `docker compose up web inference`
- Open `http://127.0.0.1:8787/` — same origin, **no wake screen**
- Or serve `frontend/` locally with `config.js` pointing at `http://127.0.0.1:8787/api/v1` and `TAGR_WAKE_BACKEND = false`

```bash
cp config.example.js config.js
# edit for local API
npx serve .
```

## Build

`npm run build` writes `config.js` from Vercel env vars before deploy.
