import { Hono } from "hono";
import type { AppEnv } from "../env";
import { createDb } from "../db/client";
import { requireAuth } from "../middleware/auth";
import { uploadImage, getImageUrl } from "../storage";
import { enqueuePhoto } from "../batcher";

const photos = new Hono<AppEnv>();

photos.post("/upload", requireAuth, async (c) => {
  const currentUserId = c.get("userId");
  const body = await c.req.parseBody();

  const images: File[] = [];
  for (const [, value] of Object.entries(body)) {
    if (value instanceof File) {
      images.push(value);
    }
  }

  if (images.length === 0) {
    return c.json({ detail: "At least one image is required" }, 400);
  }

  const sql = createDb(c.env);
  const uploadIds: string[] = [];

  try {
    for (const img of images) {
      const photoId = crypto.randomUUID();
      const ext = img.name.includes(".") ? img.name.split(".").pop() : "jpg";
      const now = new Date();
      const storageKey = `uploads/${now.getUTCFullYear()}/${String(now.getUTCMonth() + 1).padStart(2, "0")}/${String(now.getUTCDate()).padStart(2, "0")}/${photoId}.${ext}`;

      const fileBytes = await img.arrayBuffer();
      await uploadImage(c.env, fileBytes, storageKey, img.type || "image/jpeg");

      await sql`
        INSERT INTO photos (id, owner_id, storage_url, status)
        VALUES (${photoId}::uuid, ${currentUserId}::uuid, ${storageKey}, 'pending')
      `;

      uploadIds.push(photoId);
    }

    for (const photoId of uploadIds) {
      const rows = await sql`
        SELECT storage_url FROM photos WHERE id = ${photoId}::uuid
      `;
      const storageUrl = getImageUrl(c.env, rows[0].storage_url as string, true);
      await enqueuePhoto(c.env, photoId, storageUrl);
    }

    return c.json({ upload_ids: uploadIds, status: "pending" }, 202);
  } finally {
    await sql.end({ timeout: 5 });
  }
});

photos.get("/:photo_id/status", async (c) => {
  const photoId = c.req.param("photo_id");
  const sql = createDb(c.env);
  try {
    const rows = await sql`
      SELECT id, status FROM photos WHERE id = ${photoId}::uuid
    `;
    if (rows.length === 0) {
      return c.json({ detail: "Photo not found" }, 404);
    }
    return c.json({ photo_id: rows[0].id, status: rows[0].status });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

photos.get("/:photo_id/tags", async (c) => {
  const photoId = c.req.param("photo_id");
  const sql = createDb(c.env);
  try {
    const photoRows = await sql`SELECT id FROM photos WHERE id = ${photoId}::uuid`;
    if (photoRows.length === 0) {
      return c.json({ detail: "Photo not found" }, 404);
    }

    const tags = await sql`
      SELECT pt.id, pt.user_id, u.username, pt.bbox_x, pt.bbox_y,
             pt.bbox_width, pt.bbox_height, pt.confidence, pt.source
      FROM photo_tags pt
      JOIN users u ON pt.user_id = u.id
      WHERE pt.photo_id = ${photoId}::uuid
    `;

    return c.json({
      photo_id: photoId,
      tags: tags.map((tag) => ({
        tag_id: tag.id,
        user_id: tag.user_id,
        username: tag.username,
        bbox: {
          x: tag.bbox_x,
          y: tag.bbox_y,
          width: tag.bbox_width,
          height: tag.bbox_height,
        },
        confidence: tag.confidence,
        source: tag.source,
      })),
    });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

photos.patch("/:photo_id/tags/:tag_id", requireAuth, async (c) => {
  const photoId = c.req.param("photo_id");
  const tagId = c.req.param("tag_id");
  const currentUserId = c.get("userId");
  const payload = await c.req.json<{
    action?: string;
    new_user_id?: string;
  }>();

  const sql = createDb(c.env);
  try {
    const tagRows = await sql`
      SELECT id, photo_id, user_id FROM photo_tags
      WHERE id = ${tagId}::uuid
    `;
    const tag = tagRows[0];
    if (!tag || String(tag.photo_id) !== photoId) {
      return c.json({ detail: "Tag not found on this photo" }, 404);
    }

    if (payload.action === "remove") {
      await sql`DELETE FROM photo_tags WHERE id = ${tagId}::uuid`;
      return c.json({ updated: true });
    }

    if (payload.action !== "reassign") {
      return c.json({ detail: "Action must be 'reassign' or 'remove'" }, 400);
    }

    if (!payload.new_user_id) {
      return c.json({ detail: "new_user_id is required for reassign action" }, 400);
    }

    const userRows = await sql`
      SELECT id FROM users WHERE id = ${payload.new_user_id}::uuid
    `;
    if (userRows.length === 0) {
      return c.json({ detail: "New user not found" }, 404);
    }

    await sql`
      UPDATE photo_tags
      SET user_id = ${payload.new_user_id}::uuid,
          source = 'manual',
          confidence = NULL
      WHERE id = ${tagId}::uuid
    `;

    const emb = Array.from({ length: 512 }, () => {
      const u = 1 - Math.random();
      const v = Math.random();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    });
    const norm = Math.sqrt(emb.reduce((sum, x) => sum + x * x, 0));
    const cropEmbedding = emb.map((x) => x / norm);

    await sql`
      INSERT INTO face_embeddings (user_id, embedding, source, source_photo_id)
      VALUES (
        ${payload.new_user_id}::uuid,
        ${JSON.stringify(cropEmbedding)}::vector,
        'correction',
        ${photoId}::uuid
      )
    `;

    await sql`
      INSERT INTO notifications (user_id, type, photo_id, actor_user_id, is_read)
      VALUES (
        ${payload.new_user_id}::uuid,
        'tagged_in_photo',
        ${photoId}::uuid,
        ${currentUserId}::uuid,
        false
      )
    `;

    return c.json({ updated: true });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

photos.post("/:photo_id/tags", requireAuth, async (c) => {
  const photoId = c.req.param("photo_id");
  const currentUserId = c.get("userId");
  const payload = await c.req.json<{
    user_id?: string;
    bbox?: { x?: number; y?: number; width?: number; height?: number };
  }>();

  if (!payload.user_id) {
    return c.json({ detail: "user_id is required" }, 400);
  }

  const sql = createDb(c.env);
  try {
    const userRows = await sql`
      SELECT id FROM users WHERE id = ${payload.user_id}::uuid
    `;
    if (userRows.length === 0) {
      return c.json({ detail: "Target user not found" }, 404);
    }

    const bbox = payload.bbox || {};
    const tagRows = await sql`
      INSERT INTO photo_tags (
        photo_id, user_id, bbox_x, bbox_y, bbox_width, bbox_height,
        confidence, source
      )
      VALUES (
        ${photoId}::uuid,
        ${payload.user_id}::uuid,
        ${bbox.x ?? null},
        ${bbox.y ?? null},
        ${bbox.width ?? null},
        ${bbox.height ?? null},
        NULL,
        'manual'
      )
      RETURNING id
    `;

    await sql`
      INSERT INTO notifications (user_id, type, photo_id, actor_user_id, is_read)
      VALUES (
        ${payload.user_id}::uuid,
        'tagged_in_photo',
        ${photoId}::uuid,
        ${currentUserId}::uuid,
        false
      )
    `;

    return c.json({ tag_id: tagRows[0].id, created: true });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

export default photos;
