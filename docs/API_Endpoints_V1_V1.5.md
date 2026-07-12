# API Endpoints Specification — V1 / V1.5

Base path assumed: `/api/v1`

---

## FR1 — Authentication & Enrollment

### `POST /auth/register`
Register a new user with mobile number + username.
- Body: `{ mobile_number, username }`
- Action: creates user row (unverified), triggers OTP send (mocked/logged in V1, real SMS in V1.5)
- Response: `{ user_id, otp_sent: true }`

### `POST /auth/verify-otp`
Verify OTP sent to mobile number.
- Body: `{ mobile_number, otp }`
- Response: `{ verified: true, token }` or error

### `POST /auth/enroll-face`
Submit live face capture for embedding enrollment (called right after OTP verification, or at login if re-enrollment needed).
- Body: `multipart/form-data` — `image` (captured frame), `user_id`
- Action: runs face detection + embedding, stores as canonical reference embedding (FR1.3)
- Response: `{ enrolled: true, embedding_id }` or `{ enrolled: false, reason: "no_face_detected" }`

### `POST /auth/login`
Login with mobile number (OTP flow) or session resume.
- Body: `{ mobile_number, otp }`
- Response: `{ token, user_id }`

### `GET /auth/me`
Get current logged-in user profile.
- Response: `{ user_id, username, mobile_number, created_at }`

---

## FR2 — Upload & Inference Pipeline

### `POST /photos/upload`
Upload one or more photos.
- Body: `multipart/form-data` — `images[]`
- Action: stores each image in object storage, creates Postgres row per image with `status: pending`, pushes URL to batcher
- Response: `{ upload_ids: [...], status: "pending" }`

### `GET /photos/{photo_id}/status`
Poll processing status of an uploaded photo (used in V1/local or as fallback to websocket in V1.5).
- Response: `{ photo_id, status: "pending" | "processing" | "processed" | "failed" }`

### `WS /ws/photos/{user_id}`
Websocket channel (V1.5) — server pushes status updates as photos complete processing.
- Message pushed: `{ photo_id, status: "processed", tagged_users: [...] }`

### `POST /internal/inference-callback` *(internal use — called by RunPod/local inference worker only)*
Callback endpoint hit by the inference layer once a batch finishes processing.
- Body: `{ batch_id, results: [ { photo_id, faces: [ { bbox, embedding, matched_user_id, confidence } ] } ] }`
- Action: writes embeddings + tags to Postgres, marks photos `processed`, triggers FR5 notifications
- Response: `{ acknowledged: true }`

---

## FR3 — Auto-Tagging & Manual Correction

### `GET /photos/{photo_id}/tags`
Get all current tags (auto + manual) on a photo.
- Response: `{ photo_id, tags: [ { user_id, username, bbox, confidence, source: "auto"|"manual" } ] }`

### `PATCH /photos/{photo_id}/tags/{tag_id}`
Correct a wrong tag — reassign to correct user or remove.
- Body: `{ action: "reassign" | "remove", new_user_id? }`
- Action: on reassign, stores corrected face crop's embedding against new_user_id (FR3.4)
- Response: `{ updated: true }`

### `POST /photos/{photo_id}/tags`
Manually add a tag not caught by auto-detection.
- Body: `{ user_id, bbox }`
- Response: `{ tag_id, created: true }`

---

## FR4 — Embedding Storage

### `GET /users/{user_id}/embeddings`
List stored embeddings for a user (admin/debug use, not typically user-facing).
- Response: `{ user_id, embeddings: [ { embedding_id, source: "enrollment"|"correction", created_at } ] }`

*(No public create/delete endpoint in V1/V1.5 — embeddings are only written internally via FR1.3 enrollment and FR3.4 corrections.)*

---

## FR5 — Notifications

### `GET /notifications`
Get current user's notifications.
- Query: `?unread_only=true`
- Response: `{ notifications: [ { notification_id, type: "tagged_in_photo", photo_id, actor_user_id, created_at, read } ] }`

### `PATCH /notifications/{notification_id}/read`
Mark a notification as read.
- Response: `{ updated: true }`

*(Internal trigger, not a client-facing endpoint: on FR2's inference-callback completing, a notification row is created per tagged user.)*

---

## FR6 — Gallery & Comments

### `GET /users/{user_id}/gallery`
Get all photos a user is tagged in (their personal gallery).
- Query: `?page=&limit=`
- Response: `{ photos: [ { photo_id, url, uploaded_by, uploaded_at, tagged_users: [...] } ] }`

### `GET /photos/{photo_id}`
Get full photo detail including tags and comments.
- Response: `{ photo_id, url, owner_id, tags: [...], comments: [...] }`

### `POST /photos/{photo_id}/comments`
Add a comment to a photo.
- Body: `{ text }`
- Response: `{ comment_id, created: true }`

### `GET /photos/{photo_id}/comments`
List comments on a photo.
- Response: `{ comments: [ { comment_id, user_id, username, text, created_at } ] }`

---

## FR7 — Social Graph

### `GET /friends/suggestions`
Get pending friend suggestions generated from photo co-appearance.
- Response: `{ suggestions: [ { user_id, username, mutual_photo_count } ] }`

### `POST /friends/request`
Explicitly send a friend request to another user.
- Body: `{ target_user_id }`
- Response: `{ request_id, status: "pending" }`

### `POST /friends/request/{request_id}/respond`
Accept or reject a friend request (explicit or from suggestion).
- Body: `{ action: "accept" | "reject" }`
- Response: `{ updated: true }`

### `GET /friends`
List current friends.
- Response: `{ friends: [ { user_id, username, since } ] }`

---

## Summary Table

| FR | Endpoints |
|---|---|
| FR1 | `POST /auth/register`, `POST /auth/verify-otp`, `POST /auth/enroll-face`, `POST /auth/login`, `GET /auth/me` |
| FR2 | `POST /photos/upload`, `GET /photos/{id}/status`, `WS /ws/photos/{user_id}`, `POST /internal/inference-callback` |
| FR3 | `GET /photos/{id}/tags`, `PATCH /photos/{id}/tags/{tag_id}`, `POST /photos/{id}/tags` |
| FR4 | `GET /users/{id}/embeddings` |
| FR5 | `GET /notifications`, `PATCH /notifications/{id}/read` |
| FR6 | `GET /users/{id}/gallery`, `GET /photos/{id}`, `POST /photos/{id}/comments`, `GET /photos/{id}/comments` |
| FR7 | `GET /friends/suggestions`, `POST /friends/request`, `POST /friends/request/{id}/respond`, `GET /friends` |

*Note: Access-control (revoke/restrict) endpoints and consent-management endpoints are intentionally excluded — deferred to V3 per the SRS.*
