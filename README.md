# 🏷️ Tagr — AI-Powered Photo Tagging Platform

Tagr is a self-hosted, AI-powered photo tagging platform that automatically detects and identifies faces in uploaded photos using deep learning. It combines a **FastAPI** backend with an **InsightFace** inference service, **PostgreSQL + pgvector** for face embedding storage & similarity search, and **MinIO** for S3-compatible object storage — all orchestrated via **Docker Compose**. 

---

## ✨ Features

- **OTP-Based Authentication** — Register & login with mobile number + mock OTP verification, JWT-issued sessions
- **Face Enrollment** — Upload a selfie to create a 512-dimensional face embedding as your identity anchor
- **Batch Photo Upload** — Upload one or more photos; they're queued, batched, and sent to the inference service automatically
- **AI Face Detection & Recognition** — InsightFace (`buffalo_l`) detects faces, extracts embeddings, and matches them against enrolled users via pgvector cosine similarity
- **Auto & Manual Tagging** — Faces are auto-tagged when a match exceeds the similarity threshold; users can manually add, reassign, or remove tags
- **Social Graph** — Friend suggestions based on photo co-appearances, friend requests, and friendships
- **Gallery & Comments** — Browse tagged photos per user, view photo details, and leave comments
- **Notifications** — Real-time notification system for tags, friend requests, and social interactions
- **Static Frontend** — Built-in HTML/JS frontend served by FastAPI

---

## 🏗️ Architecture

```
┌──────────────┐       ┌──────────────┐       ┌──────────────────┐
│              │       │              │       │                  │
│   Frontend   │◄─────►│  Web (API)   │◄─────►│   PostgreSQL     │
│  (Static UI) │       │   FastAPI    │       │   + pgvector     │
│  Port 8787   │       │   Port 8000  │       │   Port 5432      │
│              │       │              │       │                  │
└──────────────┘       └──────┬───────┘       └──────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
              ┌─────▼──────┐     ┌──────▼─────┐
              │            │     │            │
              │ Inference  │     │   MinIO    │
              │ InsightFace│     │  (S3 Obj   │
              │ Port 8001  │     │  Storage)  │
              │            │     │  Port 9000 │
              └────────────┘     └────────────┘
```

| Service       | Container        | Port(s)     | Description                                      |
|---------------|------------------|-------------|--------------------------------------------------|
| **db**        | `tagr-db`        | `5432`      | PostgreSQL 16 with pgvector extension             |
| **storage**   | `tagr-storage`   | `9000/9001` | MinIO object storage (API / Console)              |
| **web**       | `tagr-web`       | `8787`      | FastAPI API + static UI (uvicorn)                 |
| **inference** | `tagr-inference` | `8001`      | Face detection & embedding service (InsightFace)  |

### 🖥️ Frontend Clients

* **Static Web UI (Active/Primary)**: The mobile-first web UI lives in [app/static/](app/static/) (`index.html`, `css/app.css`, `js/*.js`). It is served by the `web` service at `http://localhost:8787/`. A copy also lives at the repo root as `index.html` for GitHub Pages.
* **React Native Frontend (Optional)**: A React Native / Expo codebase exists in [frontend/](frontend/). This mobile/client build is **not** included in the Docker Compose configuration. If you wish to run or work on it, you can do so manually by navigating to `frontend/`, installing node modules, and starting the Expo server:
  ```bash
  cd frontend
  npm install
  npm start
  ```

---

## 🛠️ Tech Stack

| Layer           | Technology                                                          |
|-----------------|---------------------------------------------------------------------|
| **API**         | Python 3.11, FastAPI, SQLAlchemy, psycopg, PyJWT, boto3             |
| **Database**    | PostgreSQL 16 + pgvector (cosine similarity search)                 |
| **Auth**        | JWT (PyJWT) with mock OTP flow                                      |
| **ML/Inference**| InsightFace (`buffalo_l`), ONNX Runtime, OpenCV                     |
| **Storage**     | MinIO (S3-compatible), Boto3                                        |
| **Frontend**    | Vanilla HTML/CSS/JS (mobile-first UI served by FastAPI)             |
| **Web UI**      | Static HTML in `frontend/` (Vercel) or served by FastAPI in dev   |
| **Mobile App**  | React Native & Expo (optional, `mobile-frontend/`)                  |
| **Infra**       | Docker, Docker Compose                                              |

---

## 🚀 Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/) installed
- ~4 GB disk space (InsightFace model downloads on first run)

### 1. Clone the Repository

```bash
git clone https://github.com/ampli-xD/tagr.git
cd tagr
```

### 2. Configure Environment

Copy the example environment file and adjust values if needed:

```bash
cp .env.example .env
```

The default `.env` ships with sensible development defaults:

| Variable              | Default                  | Description                    |
|-----------------------|--------------------------|--------------------------------|
| `POSTGRES_HOST`       | `localhost`              | PostgreSQL host                |
| `POSTGRES_PORT`       | `5432`                   | PostgreSQL port                |
| `POSTGRES_DB`         | `tagr_db`                | Database name                  |
| `POSTGRES_USER`       | `postgres`               | Database user                  |
| `POSTGRES_PASSWORD`   | `postgres`               | Database password              |
| `MINIO_HOST`          | `localhost`              | MinIO host                     |
| `MINIO_PORT`          | `9000`                   | MinIO API port                 |
| `MINIO_CONSOLE_PORT`  | `9001`                   | MinIO console port             |
| `MINIO_ROOT_USER`     | `minioadmin`             | MinIO access key               |
| `MINIO_ROOT_PASSWORD` | `minioadmin`             | MinIO secret key               |
| `WEB_PORT`            | `8787`                   | FastAPI host port (maps to 8000 in container) |
| `INFERENCE_PORT`      | `8001`                   | Inference service port         |
| `INFERENCE_DEVICE`    | `cpu`                    | `cpu` or `gpu`                 |

> **Note:** Docker Compose automatically overrides hostnames to Docker service names (`db`, `storage`, `inference`) for inter-container communication.

### 3. Build & Start Services

```bash
docker-compose up -d --build
```

This starts **db**, **storage**, **inference**, and the **web** API on port **8787**.

Wait for all services to become healthy:

```bash
docker-compose ps
```

### 4. Access the Application

| What                    | URL                                |
|-------------------------|------------------------------------|
| **Web UI (Static)**     | http://localhost:8787              |
| **API Health**          | http://localhost:8787/api/v1/health |
| **MinIO Console**       | http://localhost:9001              |
| **Inference Health**    | http://localhost:8001              |

---

## 📁 Project Structure

```
tagr/
├── app/                        # FastAPI backend + static UI
│   ├── main.py                 # FastAPI app (API + static mount)
│   ├── auth.py                 # Auth & enrollment routes
│   ├── photos.py               # Photo upload & tagging
│   ├── social.py               # Gallery, friends, notifications
│   ├── internal.py             # Inference callback
│   ├── batcher.py              # In-memory photo batcher
│   ├── database.py             # SQLAlchemy engine/session
│   ├── models.py               # ORM models
│   ├── storage.py              # MinIO via boto3
│   └── static/                 # Mobile-first web UI (HTML/CSS/JS)
├── frontend/                   # Static web UI for Vercel
├── mobile-frontend/            # Optional React Native/Expo app
├── inference/                  # Face detection & embedding microservice
│   ├── main.py                 # RunPod-compatible inference worker
│   ├── core.py                 # InsightFace processing logic
│   ├── handler.py              # RunPod handler + callback support
│   ├── requirements.txt        # Python dependencies for inference
│   └── Dockerfile              # Inference container build
├── v1-migration-backend/       # Legacy Cloudflare Worker (deprecated)
├── docker-compose.yml          # Multi-service orchestration
├── Dockerfile                  # FastAPI web container
├── requirements.txt            # Python API dependencies
├── tagr_schema_v1.sql          # Database schema (auto-applied on first run)
├── .env                        # Environment configuration
└── .gitignore                  # Git ignore rules
```

---

## 📡 API Reference

All API endpoints are prefixed with `/api/v1`. Interactive docs available at `/api/v1/docs`.

### Authentication & Enrollment

| Method | Endpoint                 | Description                          | Auth |
|--------|--------------------------|--------------------------------------|------|
| POST   | `/auth/register`         | Register with mobile number & username | ❌ |
| POST   | `/auth/verify-otp`       | Verify OTP and receive JWT token     | ❌   |
| POST   | `/auth/request-login-otp`| Request OTP for login                | ❌   |
| POST   | `/auth/login`            | Login with mobile + OTP              | ❌   |
| POST   | `/auth/enroll-face`      | Upload selfie for face enrollment    | ❌   |
| GET    | `/auth/me`               | Get current user profile             | ✅   |

### Photos & Tagging

| Method | Endpoint                         | Description                        | Auth |
|--------|----------------------------------|------------------------------------|------|
| POST   | `/photos/upload`                 | Upload one or more photos          | ✅   |
| GET    | `/photos/{photo_id}/status`      | Poll photo processing status       | ❌   |
| GET    | `/photos/{photo_id}/tags`        | Get all tags on a photo            | ❌   |
| PATCH  | `/photos/{photo_id}/tags/{tag_id}` | Correct/remove a tag             | ✅   |
| POST   | `/photos/{photo_id}/tags`        | Manually add a tag                 | ✅   |

### Social, Gallery & Notifications

| Method | Endpoint                                    | Description                       | Auth |
|--------|---------------------------------------------|-----------------------------------|------|
| GET    | `/users/{user_id}/gallery`                  | Get user's tagged photos          | ✅   |
| GET    | `/photos/{photo_id}`                        | Get photo details with tags & comments | ✅ |
| POST   | `/photos/{photo_id}/comments`               | Add a comment                     | ✅   |
| GET    | `/photos/{photo_id}/comments`               | List comments on a photo          | ❌   |
| GET    | `/notifications`                            | Get user's notifications          | ✅   |
| PATCH  | `/notifications/{notification_id}/read`     | Mark notification as read         | ✅   |
| GET    | `/friends/suggestions`                      | Get friend suggestions (co-appearances) | ✅ |
| POST   | `/friends/request`                          | Send a friend request             | ✅   |
| POST   | `/friends/request/{request_id}/respond`     | Accept or reject a friend request | ✅   |
| GET    | `/friends`                                  | List current friends              | ✅   |
| GET    | `/users/{user_id}/embeddings`               | Debug: list user's face embeddings | ✅  |

### Internal

| Method | Endpoint                       | Description                               |
|--------|--------------------------------|-------------------------------------------|
| POST   | `/internal/inference-callback` | Receives results from the inference service |

---

## ⚙️ How It Works

### Face Recognition Pipeline

```
1. User enrolls face  ──►  Selfie sent to Inference  ──►  512-d embedding stored in pgvector
                                                             │
2. User uploads photo  ──►  Queued in Batcher  ──►  Batch sent to Inference  ──►  Faces detected
                                                                                       │
3. Each detected face embedding  ──►  pgvector cosine similarity search  ──►  Match found?
                                                                                  │
                                                          ┌──────────────────────┐│
                                                          │  YES (≥ threshold)   ├┘
                                                          │  → Auto-tag created  │
                                                          │  → Notification sent │
                                                          └──────────────────────┘
```

1. **Enrollment** — A user uploads a selfie. The inference service (InsightFace `buffalo_l`) extracts a normalized 512-dimensional face embedding, which is stored in PostgreSQL via the pgvector extension.

2. **Photo Upload & Batching** — Uploaded photos are stored in MinIO and queued in an in-memory batcher. The batcher flushes when the batch size is reached or a timeout elapses.

3. **Inference** — The inference service receives a batch of image URLs, downloads each from MinIO, runs face detection, and returns bounding boxes + embeddings.

4. **Matching** — The web service receives inference results via callback, performs cosine similarity search against all enrolled embeddings using pgvector's `<=>` operator, and auto-tags faces that exceed the similarity threshold.

5. **Corrections** — Users can manually reassign or remove incorrect tags. Corrections generate new reference embeddings to improve future accuracy.

---

## 🧪 Development

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f worker
docker-compose logs -f inference
```

### Rebuild a Single Service

```bash
docker-compose up -d --build worker
```

### Reset Database

```bash
docker-compose down -v   # Removes volumes (data)
docker-compose up -d --build
```

### Run Worker Without Docker (host pywrangler)

```bash
docker compose up -d db storage inference
cd v1-migration-backend
cp .dev.vars.example .dev.vars
uv sync
uv run pywrangler dev
```

> Make sure PostgreSQL and MinIO are running (via Docker Compose) and `.dev.vars` points at `localhost`.

---

## 📝 License

This project is licensed under the **MIT License** — see the [LICENSE.md](docs/LICENSE.md) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](docs/CONTRIBUTING.md) for details on our code of conduct, coding standards, commit conventions, and the pull request process.
