# Tagr web frontend (Vercel)

Static single-page app deployed separately from the FastAPI backend.

## Vercel setup

1. Import this repo and set **Root Directory** to `frontend`.
2. Add environment variable:
   - `TAGR_API_URL` = your production API base, e.g. `https://api.yourdomain.com/api/v1`
3. Deploy.

The build writes `config.js` from `TAGR_API_URL`. Without it, the app runs in demo mode on `*.vercel.app`.

## Local preview

```bash
cp config.example.js config.js
# edit config.js with your API URL
npx serve .
```

## Backend CORS

Set on the API server (production branch):

```env
CORS_ALLOW_ORIGINS=https://your-app.vercel.app
```

Or `*` for testing.
