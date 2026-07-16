import { Hono } from "hono";
import type { AppEnv } from "../env";
import { createDb } from "../db/client";
import { requireAuth } from "../middleware/auth";
import { getImageUrl } from "../storage";

const internal = new Hono<AppEnv>();

internal.post("/inference-callback", async (c) => {
  const payload = await c.req.json<{
    batch_id?: string;
    results?: Array<{
      photo_id?: string;
      faces?: Array<{
        bbox?: Record<string, number>;
        embedding?: number[];
        confidence?: number;
      }>;
    }>;
  }>();

  const results = payload.results || [];
  const batchId = payload.batch_id;
  const similarityThreshold = Number.parseFloat(c.env.SIMILARITY_THRESHOLD || "0.35");
  const maxDistance = 1.0 - similarityThreshold;

  console.log(
    `Received inference callback for batch: ${batchId}. Images count: ${results.length}`,
  );

  const sql = createDb(c.env);
  try {
    const countRows = await sql`SELECT COUNT(*)::int AS count FROM face_embeddings`;
    console.log(
      `DEBUG: total face_embeddings visible to this session: ${countRows[0].count}`,
    );

    for (const item of results) {
      const photoId = item.photo_id;
      if (!photoId) continue;

      const photoRows = await sql`
        SELECT id, owner_id FROM photos WHERE id = ${photoId}::uuid
      `;
      if (photoRows.length === 0) {
        console.log(`Warning: Photo ${photoId} not found in database.`);
        continue;
      }

      const photo = photoRows[0];
      const faces = item.faces || [];

      for (const face of faces) {
        const bbox = face.bbox || {};
        const embedding = face.embedding || [];
        const confidence = face.confidence ?? 1.0;

        if (embedding.length !== 512) continue;

        const embeddingLiteral = JSON.stringify(embedding);
        const matchRows = await sql`
          SELECT user_id, (embedding <=> ${embeddingLiteral}::vector) AS distance
          FROM face_embeddings
          WHERE embedding <=> ${embeddingLiteral}::vector <= ${maxDistance}
          ORDER BY distance ASC
          LIMIT 1
        `;

        if (matchRows.length > 0) {
          const matchedUserId = matchRows[0].user_id as string;
          const distance = matchRows[0].distance as number;
          console.log(
            `Matched face in photo ${photoId} to user ${matchedUserId} (distance: ${distance.toFixed(4)})`,
          );

          const xmin = bbox.xmin ?? bbox.x;
          const ymin = bbox.ymin ?? bbox.y;
          const xmax = bbox.xmax;
          const yminVal = ymin ?? 0;
          const xminVal = xmin ?? 0;
          const width =
            xmax !== undefined && xmin !== undefined ? xmax - xmin : 0.1;
          const height =
            bbox.ymax !== undefined && ymin !== undefined
              ? bbox.ymax - ymin
              : 0.1;

          await sql`
            INSERT INTO photo_tags (
              photo_id, user_id, bbox_x, bbox_y, bbox_width, bbox_height,
              confidence, source
            )
            VALUES (
              ${photoId}::uuid,
              ${matchedUserId}::uuid,
              ${xminVal},
              ${yminVal},
              ${width},
              ${height},
              ${confidence},
              'auto'
            )
          `;

          await sql`
            INSERT INTO notifications (user_id, type, photo_id, actor_user_id, is_read)
            VALUES (
              ${matchedUserId}::uuid,
              'tagged_in_photo',
              ${photoId}::uuid,
              ${photo.owner_id}::uuid,
              false
            )
          `;
        } else {
          const closestRows = await sql`
            SELECT user_id, (embedding <=> ${embeddingLiteral}::vector) AS distance
            FROM face_embeddings
            ORDER BY distance ASC
            LIMIT 1
          `;
          if (closestRows.length > 0) {
            const closestSim = 1.0 - (closestRows[0].distance as number);
            console.log(
              `No match found for face in photo ${photoId} (closest was user ${closestRows[0].user_id}, similarity: ${closestSim.toFixed(4)})`,
            );
          } else {
            console.log(
              `No match found for face in photo ${photoId} (no embeddings in DB at all)`,
            );
          }
        }
      }

      await sql`
        UPDATE photos
        SET status = 'processed',
            processed_at = NOW(),
            batch_id = ${batchId ?? null}::uuid
        WHERE id = ${photoId}::uuid
      `;
    }

    return c.json({ acknowledged: true });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

export default internal;
