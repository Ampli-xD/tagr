-- =====================================================================
-- Tagr — Postgres Schema (V1 / V1.5)
-- =====================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector, for face embeddings

-- =====================================================================
-- 1. users
-- =====================================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mobile_number   VARCHAR(15) UNIQUE NOT NULL,
    username        VARCHAR(30) UNIQUE NOT NULL,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- 2. otp_requests
-- =====================================================================
CREATE TABLE otp_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mobile_number   VARCHAR(15) NOT NULL,
    otp_code        VARCHAR(6) NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    verified        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_otp_mobile ON otp_requests(mobile_number);

-- =====================================================================
-- 3. photos
-- (created before face_embeddings so the FK below can reference it directly)
-- =====================================================================
CREATE TABLE photos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    storage_url     TEXT NOT NULL,          -- local path (V1) or R2 URL (V1.5)
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processing', 'processed', 'failed')),
    batch_id        UUID,                   -- inference batch this photo was sent in
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX idx_photos_owner ON photos(owner_id);
CREATE INDEX idx_photos_status ON photos(status);
CREATE INDEX idx_photos_batch ON photos(batch_id);

-- =====================================================================
-- 4. face_embeddings
-- =====================================================================
CREATE TABLE face_embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    embedding       VECTOR(512),            -- dimension depends on model used
    source          VARCHAR(20) NOT NULL CHECK (source IN ('enrollment', 'correction')),
    source_photo_id UUID REFERENCES photos(id) ON DELETE SET NULL,  -- null for enrollment
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_face_embeddings_user ON face_embeddings(user_id);
-- NOTE: No approximate (IVFFlat/HNSW) index on the embedding column.
-- IVFFlat is an APPROXIMATE index: with a small/moderate number of vectors and
-- the default single-probe search, "ORDER BY embedding <=> probe LIMIT 1" can
-- return zero candidates, silently missing valid face matches. At this scale an
-- exact sequential KNN scan is both correct and fast, so we intentionally omit
-- the vector index. Reintroduce a tuned HNSW index only at large scale, e.g.:
--   CREATE INDEX idx_face_embeddings_vector ON face_embeddings
--     USING hnsw (embedding vector_cosine_ops);

-- =====================================================================
-- 5. photo_tags
-- =====================================================================
CREATE TABLE photo_tags (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id        UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bbox_x          FLOAT,
    bbox_y          FLOAT,
    bbox_width      FLOAT,
    bbox_height     FLOAT,
    confidence      FLOAT,                  -- null if manually added
    source          VARCHAR(10) NOT NULL CHECK (source IN ('auto', 'manual')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_photo_tags_photo ON photo_tags(photo_id);
CREATE INDEX idx_photo_tags_user ON photo_tags(user_id);

-- =====================================================================
-- 6. comments
-- =====================================================================
CREATE TABLE comments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id        UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_comments_photo ON comments(photo_id);

-- =====================================================================
-- 7. notifications
-- =====================================================================
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            VARCHAR(30) NOT NULL DEFAULT 'tagged_in_photo',
    photo_id        UUID REFERENCES photos(id) ON DELETE CASCADE,
    actor_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user ON notifications(user_id, is_read);

-- =====================================================================
-- 8. friend_requests
-- =====================================================================
CREATE TABLE friend_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    origin          VARCHAR(20) NOT NULL DEFAULT 'explicit'
                        CHECK (origin IN ('explicit', 'suggestion')),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'accepted', 'rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    responded_at    TIMESTAMPTZ,
    UNIQUE (from_user_id, to_user_id)
);

CREATE INDEX idx_friend_requests_to ON friend_requests(to_user_id, status);

-- =====================================================================
-- 9. friendships
-- =====================================================================
CREATE TABLE friendships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_b_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (user_a_id < user_b_id),   -- enforce single row per pair regardless of order
    UNIQUE (user_a_id, user_b_id)
);

CREATE INDEX idx_friendships_a ON friendships(user_a_id);
CREATE INDEX idx_friendships_b ON friendships(user_b_id);

-- =====================================================================
-- End of schema
-- =====================================================================
