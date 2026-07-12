# Software Requirements Specification — V1 & V1.5

## 1. Purpose
This SRS defines the requirements for two closely related releases that share the exact same architecture and codebase:

- **V1** — Local deployment. Used to build and debug the full pipeline end-to-end on a developer machine, with no cloud costs or network latency.
- **V1.5** — Cloud deployment. Identical logic to V1, but backing services are swapped for real cloud infrastructure so the app can be used by external alpha/beta testers (friends) over the internet.

Neither V1 nor V1.5 is intended for public launch. Public launch is gated behind V2 (scale-tuned architecture) and V3 (abuse prevention, access control, formal consent/legal compliance).

## 2. Scope

### In scope (both V1 and V1.5)
- Mobile + username-based authentication with live face capture enrollment
- Async photo upload pipeline with batching
- Face detection and embedding-based auto-tagging
- Manual tag correction
- Notifications to tagged users
- Personal gallery and comments
- Basic social graph (friend suggestion + explicit add)

### Out of scope (deferred to V3)
- Adaptive/lowered-threshold recheck for anti-gaming manual corrections
- Embedding distance-based dedup/drift rejection logic
- Access control: revoke/restrict a tagged person's access to a photo
- Formal privacy/consent/legal compliance flows (BIPA/GDPR/DPDP-style consent, data deletion requests, etc.)

## 3. Deployment Targets

| Component | V1 (Local) | V1.5 (Cloud) |
|---|---|---|
| API server | FastAPI via `uvicorn`, single process, localhost | FastAPI deployed on a cloud host (e.g. Railway/Fly.io/EC2) |
| Object storage | Local disk or MinIO (S3-compatible, run locally in Docker) | Cloudflare R2 |
| Database | Postgres in local Docker container | Managed Postgres (e.g. Supabase/Neon/RDS) |
| Inference | Local function call to the same detection/embedding model (GPU if available locally, else CPU) | RunPod serverless GPU endpoint, invoked over HTTPS |
| Batcher | In-memory, same count/timeout logic, running in-process | Same in-memory logic, running in-process on the deployed server |
| Notification delivery | DB flag + console log or simple polling from a local frontend/dev client | Real websocket push or polling from a deployed frontend to deployed backend |
| Users | Solo developer only | Closed group of friends (alpha/beta testers) |

**Design intent:** The application code (FastAPI routes, batcher, inference-calling logic, database models) must be identical between V1 and V1.5. Only configuration/environment variables and the storage/inference/DB backends change. This is achieved by abstracting storage (local disk vs. R2), inference (local call vs. RunPod HTTP call), and DB connection behind common interfaces so switching is a config change, not a code change.

## 4. Functional Requirements

### FR1 — Authentication & Enrollment
- FR1.1: User registers with a mobile number (OTP-based, can be mocked/logged to console in V1) and a unique username.
- FR1.2: During login/signup, user performs a live face capture (liveness detection not enforced in V1/V1.5).
- FR1.3: Captured face is embedded and stored as the user's canonical reference embedding in Postgres.

### FR2 — Upload & Inference Pipeline
- FR2.1: User uploads one or more photos via a FastAPI endpoint (async, non-blocking).
- FR2.2: Image is stored in the configured object storage (local disk/MinIO in V1, R2 in V1.5); a metadata row is created in Postgres with status `pending`.
- FR2.3: The stored image's URL/path is added to an in-memory batcher.
- FR2.4: Batcher flushes on whichever condition is met first:
  - Batch reaches size N (e.g. 10 images), or
  - Timeout T elapses since the first image in the current batch (e.g. 50ms)
- FR2.5: On flush, the batch of URLs is sent to the inference layer:
  - V1: direct local function call (same process or local service)
  - V1.5: HTTP request to RunPod serverless GPU endpoint
- FR2.6: Inference worker fetches images from storage, runs face detection and generates embeddings for each detected face.
- FR2.7: Embeddings are written to Postgres; corresponding row(s) status updated to `processed`.
- FR2.8: Completion triggers a callback to the FastAPI server (in V1 this can be a direct in-process callback; in V1.5 this is a real HTTP callback from RunPod).
- FR2.9: FastAPI notifies the frontend/client that processing is complete (console log/poll in V1, websocket/poll in V1.5).

### FR3 — Auto-Tagging & Manual Correction
- FR3.1: Each detected face embedding is matched against all stored user embeddings using a fixed similarity threshold (cosine similarity or equivalent) — no adaptive/lowered-threshold rechecking in V1/V1.5.
- FR3.2: Users whose embeddings match above threshold are auto-tagged in the photo.
- FR3.3: Photo owner or a tagged individual can manually correct a wrong tag (remove or reassign to the correct user).
- FR3.4: On an accepted manual correction, the corrected face crop's embedding is stored against the correct user as an additional reference embedding — no dedup or merge logic applied.

### FR4 — Embedding Storage
- FR4.1: The system stores multiple embeddings per user over time — one from initial enrollment (FR1.3), plus one per accepted manual correction (FR3.4).
- FR4.2: No distance-based rejection or merging of near-duplicate embeddings in V1/V1.5 (all accepted embeddings are stored as-is; this logic is deferred to V3).

### FR5 — Notifications
- FR5.1: A tagged user receives a notification when they appear in a newly processed photo.
- FR5.2: The notification links to the photo and shows all other users tagged in it.

### FR6 — Gallery & Comments
- FR6.1: Auto-tagged photos appear in the tagged user's personal gallery.
- FR6.2: Users can comment on any photo they are tagged in or that is visible to them.

### FR7 — Social Graph
- FR7.1: Co-appearance of two users in a photo triggers a "friend suggestion" prompt (not an automatic friend add).
- FR7.2: Users can also explicitly add another user as a friend directly, independent of co-appearance.

## 5. Non-Functional Requirements
- NFR1 (Performance): 
  - V1: no strict latency target — used for correctness testing only.
  - V1.5: inference turnaround (upload → tagged result visible) should target a few seconds per batch under light alpha-test load.
- NFR2 (Scale): 
  - V1: single developer, single image/small batch at a time.
  - V1.5: designed for a closed group of roughly 10–50 friends with low, bursty upload volume; not tuned for production-scale concurrency.
- NFR3 (Portability): Storage, database, and inference backends must be swappable via configuration/environment variables only, with no changes to core application logic, to keep V1 and V1.5 in sync.
- NFR4 (Data handling): 
  - V1: test/dummy data only, no real third-party face data required.
  - V1.5: real face data of consenting friends only; informal consent is acceptable at this stage (formal consent/legal flows deferred to V3).
- NFR5 (Observability): Basic logging of batch size, batch flush trigger (count vs. timeout), and inference latency should be present in both V1 and V1.5 to inform batching tuning ahead of V2.

## 6. Explicitly Deferred to V3
- Adaptive/lowered-threshold recheck for anti-gaming manual tag corrections.
- Embedding distance-based dedup/drift rejection (reject near-duplicate embeddings within a distance threshold; merge distinct-but-same-person embeddings).
- Access control: photo owner's ability to revoke or restrict a tagged person's access to a photo.
- Formal privacy/consent/legal compliance flows required before any public launch (e.g. explicit biometric consent capture, data deletion/export requests, region-specific compliance such as BIPA/GDPR/DPDP).

## 7. Release Gate
- V1 never leaves the developer's local machine; it exists solely to validate pipeline correctness.
- V1.5 is released only to a closed group of friends acting as alpha/beta testers, with informal consent for face data collection.
- Public launch is blocked until V2 (batching tuned against real usage data, scale-appropriate infra) and V3 (abuse prevention, access control, formal consent/legal compliance) are complete.
