# V1 Frontend — GitHub Pages

The V1 mobile-first static UI lives in `v1-migration-backend/public/index.html`. That same file is copied to the repo root as `index.html` for branch-based Pages fallback. The Worker serves it at http://localhost:8787 when you run `docker compose up`.

## Live URL

After Pages is enabled (see below):

**https://dishantwdts.github.io/tagr/**

## One-time repo setup

1. Open **GitHub → Settings → Pages**
2. Under **Build and deployment**, set **Source** to **GitHub Actions** (recommended)

   If Pages is set to **Deploy from a branch** (`v1` / root) instead, the repo must include a root `index.html` and `.nojekyll`. Without those, GitHub serves `README.md` as the homepage.

3. Push to `v1` (or run the workflow manually from the Actions tab)

The workflow file is `.github/workflows/deploy-v1-frontend-pages.yml`. It publishes `v1-migration-backend/public/index.html` as the site root `index.html`.

## Iteration workflow

1. Edit `v1-migration-backend/public/index.html` on branch `v1`
2. Copy it to the repo root if you rely on branch-based Pages: `cp v1-migration-backend/public/index.html index.html` (or run `scripts/sync-pages-preview.sh`)
3. Commit and push
4. GitHub Actions deploys automatically (usually within ~1 minute)
5. Refresh the Pages URL to see changes

For local preview with the API:

```bash
docker compose up
# open http://localhost:8787
```

## Demo mode (no backend)

On GitHub Pages, **demo mode is on by default**. The UI uses filler data and never calls the API.

1. Open the Pages URL
2. Register or log in with **any** username, mobile, and OTP
3. Gallery, friends, notifications, uploads, comments, and tags all work with mock data

Force demo locally:

```
http://localhost:8787/?demo=1
```

Use the real API instead:

```
?demo=0&api=http://localhost:8787/api/v1
```


GitHub Pages only hosts static files. The backend still runs separately (e.g. `docker compose` locally or a cloud host later).

On the hosted UI, set your API once via URL parameter:

```
https://dishantwdts.github.io/tagr/?api=http://localhost:8787/api/v1
```

That value is saved in `localStorage` for return visits. For a deployed backend, use its public URL instead:

```
https://dishantwdts.github.io/tagr/?api=https://your-api.example.com/api/v1
```

**Note:** Cross-origin API calls require CORS on the backend. The Tagr Worker API already allows all origins.
