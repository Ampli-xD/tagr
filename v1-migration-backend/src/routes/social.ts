import { Hono } from "hono";
import type { AppEnv } from "../env";
import { createDb } from "../db/client";
import { requireAuth } from "../middleware/auth";
import { getImageUrl } from "../storage";

const social = new Hono<AppEnv>();

social.get("/notifications", requireAuth, async (c) => {
  const currentUserId = c.get("userId");
  const unreadOnly = c.req.query("unread_only") === "true";

  const sql = createDb(c.env);
  try {
    const rows = unreadOnly
      ? await sql`
          SELECT n.id, n.type, n.photo_id, n.actor_user_id, n.is_read, n.created_at,
                 u.username AS actor_username
          FROM notifications n
          LEFT JOIN users u ON n.actor_user_id = u.id
          WHERE n.user_id = ${currentUserId}::uuid AND n.is_read = false
          ORDER BY n.created_at DESC
        `
      : await sql`
          SELECT n.id, n.type, n.photo_id, n.actor_user_id, n.is_read, n.created_at,
                 u.username AS actor_username
          FROM notifications n
          LEFT JOIN users u ON n.actor_user_id = u.id
          WHERE n.user_id = ${currentUserId}::uuid
          ORDER BY n.created_at DESC
        `;

    return c.json({
      notifications: rows.map((notif) => ({
        notification_id: notif.id,
        type: notif.type,
        photo_id: notif.photo_id,
        actor_user_id: notif.actor_user_id,
        actor_username: notif.actor_username,
        created_at: notif.created_at,
        read: notif.is_read,
      })),
    });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.patch("/notifications/:notification_id/read", requireAuth, async (c) => {
  const notificationId = c.req.param("notification_id");
  const currentUserId = c.get("userId");

  const sql = createDb(c.env);
  try {
    const rows = await sql`
      UPDATE notifications
      SET is_read = true
      WHERE id = ${notificationId}::uuid AND user_id = ${currentUserId}::uuid
      RETURNING id
    `;
    if (rows.length === 0) {
      return c.json({ detail: "Notification not found" }, 404);
    }
    return c.json({ updated: true });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.get("/users/:user_id/gallery", requireAuth, async (c) => {
  const userId = c.req.param("user_id");
  const page = Math.max(1, Number.parseInt(c.req.query("page") || "1", 10));
  const limit = Math.max(1, Number.parseInt(c.req.query("limit") || "20", 10));
  const offset = (page - 1) * limit;

  const sql = createDb(c.env);
  try {
    const photos = await sql`
      SELECT DISTINCT p.id, p.owner_id, p.storage_url, p.uploaded_at
      FROM photos p
      JOIN photo_tags pt ON p.id = pt.photo_id
      WHERE pt.user_id = ${userId}::uuid
      ORDER BY p.uploaded_at DESC
      OFFSET ${offset} LIMIT ${limit}
    `;

    const photosList = [];
    for (const photo of photos) {
      const tags = await sql`
        SELECT pt.user_id, u.username
        FROM photo_tags pt
        JOIN users u ON pt.user_id = u.id
        WHERE pt.photo_id = ${photo.id}::uuid
      `;

      photosList.push({
        photo_id: photo.id,
        url: getImageUrl(c.env, photo.storage_url as string, false),
        uploaded_by: photo.owner_id,
        uploaded_at: photo.uploaded_at,
        tagged_users: tags.map((tag) => ({
          user_id: tag.user_id,
          username: tag.username,
        })),
      });
    }

    return c.json({ photos: photosList });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.get("/photos/:photo_id", requireAuth, async (c) => {
  const photoId = c.req.param("photo_id");

  const sql = createDb(c.env);
  try {
    const photoRows = await sql`
      SELECT id, owner_id, storage_url, status
      FROM photos WHERE id = ${photoId}::uuid
    `;
    if (photoRows.length === 0) {
      return c.json({ detail: "Photo not found" }, 404);
    }
    const photo = photoRows[0];

    const tags = await sql`
      SELECT pt.id, pt.user_id, u.username, pt.bbox_x, pt.bbox_y,
             pt.bbox_width, pt.bbox_height, pt.confidence, pt.source
      FROM photo_tags pt
      JOIN users u ON pt.user_id = u.id
      WHERE pt.photo_id = ${photoId}::uuid
    `;

    const comments = await sql`
      SELECT c.id, c.user_id, u.username, c.text, c.created_at
      FROM comments c
      JOIN users u ON c.user_id = u.id
      WHERE c.photo_id = ${photoId}::uuid
      ORDER BY c.created_at ASC
    `;

    return c.json({
      photo_id: photo.id,
      url: getImageUrl(c.env, photo.storage_url as string, false),
      owner_id: photo.owner_id,
      status: photo.status,
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
      comments: comments.map((comment) => ({
        comment_id: comment.id,
        user_id: comment.user_id,
        username: comment.username,
        text: comment.text,
        created_at: comment.created_at,
      })),
    });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.post("/photos/:photo_id/comments", requireAuth, async (c) => {
  const photoId = c.req.param("photo_id");
  const currentUserId = c.get("userId");
  const payload = await c.req.json<{ text?: string }>();

  if (!payload.text) {
    return c.json({ detail: "Comment text is required" }, 400);
  }

  const sql = createDb(c.env);
  try {
    const photoRows = await sql`
      SELECT id FROM photos WHERE id = ${photoId}::uuid
    `;
    if (photoRows.length === 0) {
      return c.json({ detail: "Photo not found" }, 404);
    }

    const commentRows = await sql`
      INSERT INTO comments (photo_id, user_id, text)
      VALUES (${photoId}::uuid, ${currentUserId}::uuid, ${payload.text})
      RETURNING id
    `;

    return c.json({ comment_id: commentRows[0].id, created: true });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.get("/photos/:photo_id/comments", async (c) => {
  const photoId = c.req.param("photo_id");
  const sql = createDb(c.env);
  try {
    const comments = await sql`
      SELECT c.id, c.user_id, u.username, c.text, c.created_at
      FROM comments c
      JOIN users u ON c.user_id = u.id
      WHERE c.photo_id = ${photoId}::uuid
      ORDER BY c.created_at ASC
    `;

    return c.json({
      comments: comments.map((comment) => ({
        comment_id: comment.id,
        user_id: comment.user_id,
        username: comment.username,
        text: comment.text,
        created_at: comment.created_at,
      })),
    });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.get("/friends/suggestions", requireAuth, async (c) => {
  const currentUserId = c.get("userId");
  const sql = createDb(c.env);
  try {
    const rows = await sql`
      SELECT pt2.user_id AS suggested_id, u.username, COUNT(pt1.photo_id)::int AS mutual_photos
      FROM photo_tags pt1
      JOIN photo_tags pt2 ON pt1.photo_id = pt2.photo_id AND pt1.user_id != pt2.user_id
      JOIN users u ON pt2.user_id = u.id
      WHERE pt1.user_id = ${currentUserId}::uuid
        AND NOT EXISTS (
          SELECT 1 FROM friendships f
          WHERE (f.user_a_id = ${currentUserId}::uuid AND f.user_b_id = pt2.user_id)
             OR (f.user_b_id = ${currentUserId}::uuid AND f.user_a_id = pt2.user_id)
        )
        AND NOT EXISTS (
          SELECT 1 FROM friend_requests fr
          WHERE (fr.from_user_id = ${currentUserId}::uuid AND fr.to_user_id = pt2.user_id)
             OR (fr.from_user_id = pt2.user_id AND fr.to_user_id = ${currentUserId}::uuid)
        )
      GROUP BY pt2.user_id, u.username
      ORDER BY mutual_photos DESC
    `;

    return c.json({
      suggestions: rows.map((row) => ({
        user_id: row.suggested_id,
        username: row.username,
        mutual_photo_count: row.mutual_photos,
      })),
    });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.post("/friends/request", requireAuth, async (c) => {
  const currentUserId = c.get("userId");
  const payload = await c.req.json<{ target_user_id?: string }>();

  if (!payload.target_user_id) {
    return c.json({ detail: "target_user_id is required" }, 400);
  }

  if (currentUserId === payload.target_user_id) {
    return c.json({ detail: "Cannot send friend request to yourself" }, 400);
  }

  const sql = createDb(c.env);
  try {
    const targetRows = await sql`
      SELECT id FROM users WHERE id = ${payload.target_user_id}::uuid
    `;
    if (targetRows.length === 0) {
      return c.json({ detail: "Target user not found" }, 404);
    }

    const friendshipRows = await sql`
      SELECT id FROM friendships
      WHERE (user_a_id = ${currentUserId}::uuid AND user_b_id = ${payload.target_user_id}::uuid)
         OR (user_a_id = ${payload.target_user_id}::uuid AND user_b_id = ${currentUserId}::uuid)
    `;
    if (friendshipRows.length > 0) {
      return c.json({ detail: "Already friends with this user" }, 400);
    }

    const existingReq = await sql`
      SELECT id, status FROM friend_requests
      WHERE (from_user_id = ${currentUserId}::uuid AND to_user_id = ${payload.target_user_id}::uuid)
         OR (from_user_id = ${payload.target_user_id}::uuid AND to_user_id = ${currentUserId}::uuid)
      LIMIT 1
    `;
    if (existingReq.length > 0) {
      return c.json({
        request_id: existingReq[0].id,
        status: existingReq[0].status,
      });
    }

    const reqRows = await sql`
      INSERT INTO friend_requests (from_user_id, to_user_id, origin, status)
      VALUES (
        ${currentUserId}::uuid,
        ${payload.target_user_id}::uuid,
        'explicit',
        'pending'
      )
      RETURNING id
    `;

    return c.json({ request_id: reqRows[0].id, status: "pending" });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.post("/friends/request/:request_id/respond", requireAuth, async (c) => {
  const requestId = c.req.param("request_id");
  const currentUserId = c.get("userId");
  const payload = await c.req.json<{ action?: string }>();

  if (payload.action !== "accept" && payload.action !== "reject") {
    return c.json({ detail: "Action must be 'accept' or 'reject'" }, 400);
  }

  const sql = createDb(c.env);
  try {
    const reqRows = await sql`
      SELECT id, from_user_id, to_user_id, status
      FROM friend_requests
      WHERE id = ${requestId}::uuid
    `;
    const req = reqRows[0];
    if (!req || req.to_user_id !== currentUserId) {
      return c.json({ detail: "Request not found or not addressed to you" }, 404);
    }
    if (req.status !== "pending") {
      return c.json({ detail: "Request already processed" }, 400);
    }

    if (payload.action === "reject") {
      await sql`
        UPDATE friend_requests
        SET status = 'rejected', responded_at = NOW()
        WHERE id = ${requestId}::uuid
      `;
      return c.json({ updated: true });
    }

    await sql`
      UPDATE friend_requests
      SET status = 'accepted', responded_at = NOW()
      WHERE id = ${requestId}::uuid
    `;

    const sortedIds = [String(req.from_user_id), String(req.to_user_id)].sort();
    const userA = sortedIds[0];
    const userB = sortedIds[1];

    const friendshipExists = await sql`
      SELECT id FROM friendships
      WHERE user_a_id = ${userA}::uuid AND user_b_id = ${userB}::uuid
    `;
    if (friendshipExists.length === 0) {
      await sql`
        INSERT INTO friendships (user_a_id, user_b_id)
        VALUES (${userA}::uuid, ${userB}::uuid)
      `;
    }

    return c.json({ updated: true });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.get("/friends", requireAuth, async (c) => {
  const currentUserId = c.get("userId");
  const sql = createDb(c.env);
  try {
    const rows = await sql`
      SELECT u.id, u.username, f.created_at
      FROM friendships f
      JOIN users u ON (
        (u.id = f.user_a_id AND f.user_b_id = ${currentUserId}::uuid)
        OR (u.id = f.user_b_id AND f.user_a_id = ${currentUserId}::uuid)
      )
    `;

    return c.json({
      friends: rows.map((row) => ({
        user_id: row.id,
        username: row.username,
        since: row.created_at,
      })),
    });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

social.get("/users/:user_id/embeddings", requireAuth, async (c) => {
  const userId = c.req.param("user_id");
  const sql = createDb(c.env);
  try {
    const embs = await sql`
      SELECT id, source, created_at
      FROM face_embeddings
      WHERE user_id = ${userId}::uuid
      ORDER BY created_at DESC
    `;

    return c.json({
      user_id: userId,
      embeddings: embs.map((emb) => ({
        embedding_id: emb.id,
        source: emb.source,
        created_at: emb.created_at,
      })),
    });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

export default social;
