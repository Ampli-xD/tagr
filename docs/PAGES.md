# V1 Frontend — GitHub Pages

The V1 static UI lives in `app/static/index.html` and is deployed to GitHub Pages from the `v1-frontend` branch.

## Live URL

After Pages is enabled (see below):

**https://dishantwdts.github.io/tagr/**

## One-time repo setup

1. Open **GitHub → Settings → Pages**
2. Under **Build and deployment**, set **Source** to **GitHub Actions**
3. Push to `v1-frontend` (or run the workflow manually from the Actions tab)

The workflow file is `.github/workflows/deploy-v1-frontend-pages.yml`. It publishes `app/static/index.html` as the site root `index.html`.

## Iteration workflow

1. Edit `app/static/index.html` on branch `v1-frontend`
2. Commit and push
3. GitHub Actions deploys automatically (usually within ~1 minute)
4. Refresh the Pages URL to see changes

For local preview with the API:

```bash
docker compose up
# open http://localhost:8000
```

## Demo mode (no backend)

On GitHub Pages, **demo mode is on by default**. The UI uses filler data and never calls the API.

1. Open the Pages URL
2. Register or log in with **any** username, mobile, and OTP
3. Gallery, friends, notifications, uploads, comments, and tags all work with mock data

Force demo locally:

```
http://localhost:8000/?demo=1
```

Use the real API instead:

```
?demo=0&api=http://localhost:8000/api/v1
```


GitHub Pages only hosts static files. The backend still runs separately (e.g. `docker compose` locally or a cloud host later).

On the hosted UI, set your API once via URL parameter:

```
https://dishantwdts.github.io/tagr/?api=http://localhost:8000/api/v1
```

That value is saved in `localStorage` for return visits. For a deployed backend, use its public URL instead:

```
https://dishantwdts.github.io/tagr/?api=https://your-api.example.com/api/v1
```

**Note:** Cross-origin API calls require CORS on the backend. The Tagr FastAPI app already allows all origins.
