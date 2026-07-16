import type { Env } from "./env";
import { createDb } from "./db/client";

interface QueueItem {
  photoId: string;
  storageUrl: string;
}

export class PhotoBatcher implements DurableObject {
  private queue: QueueItem[] = [];
  private alarmScheduled = false;

  constructor(
    private readonly state: DurableObjectState,
    private readonly env: Env,
  ) {}

  async fetch(request: Request): Promise<Response> {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    const body = (await request.json()) as QueueItem;
    await this.addPhoto(body.photoId, body.storageUrl);
    return Response.json({ ok: true });
  }

  private async addPhoto(photoId: string, storageUrl: string): Promise<void> {
    this.queue.push({ photoId, storageUrl });
    const batchSize = Number.parseInt(this.env.BATCH_SIZE || "10", 10);

    if (this.queue.length >= batchSize) {
      await this.flush();
      return;
    }

    if (!this.alarmScheduled) {
      this.alarmScheduled = true;
      const timeoutMs = Number.parseFloat(this.env.BATCH_TIMEOUT_MS || "50");
      await this.state.storage.setAlarm(Date.now() + timeoutMs);
    }
  }

  async alarm(): Promise<void> {
    this.alarmScheduled = false;
    if (this.queue.length > 0) {
      await this.flush();
    }
  }

  private async flush(): Promise<void> {
    const batchItems = [...this.queue];
    this.queue = [];
    this.alarmScheduled = false;

    if (batchItems.length === 0) return;

    const payload = {
      images: batchItems.map((item) => ({
        image_id: item.photoId,
        url: item.storageUrl,
      })),
    };

    const photoIds = batchItems.map((item) => item.photoId);
    await this.updatePhotosStatus(photoIds, "processing");

    const batchId = crypto.randomUUID();
    const predictUrl = `${this.env.INFERENCE_URL.replace(/\/$/, "")}/predict`;

    try {
      const inferenceResponse = await fetch(predictUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!inferenceResponse.ok) {
        const text = await inferenceResponse.text();
        console.error(`Inference failed: ${inferenceResponse.status} ${text}`);
        await this.updatePhotosStatus(photoIds, "failed");
        return;
      }

      const inferenceResults = (await inferenceResponse.json()) as {
        results?: Array<{
          image_id?: string;
          faces?: Array<{
            bounding_box?: Record<string, number>;
            embedding?: number[];
            confidence?: number;
          }>;
        }>;
      };

      const callbackResults = (inferenceResults.results || []).map((result) => ({
        photo_id: result.image_id,
        faces: (result.faces || []).map((face) => ({
          bbox: face.bounding_box || {},
          embedding: face.embedding || [],
          confidence: face.confidence ?? 1.0,
        })),
      }));

      const callbackPayload = {
        batch_id: batchId,
        results: callbackResults,
      };

      const callbackResponse = await fetch(this.env.API_CALLBACK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(callbackPayload),
      });

      if (!callbackResponse.ok) {
        const text = await callbackResponse.text();
        console.error(`Callback failed: ${callbackResponse.status} ${text}`);
        await this.updatePhotosStatus(photoIds, "failed");
      }
    } catch (error) {
      console.error("Error in batch inference runner:", error);
      await this.updatePhotosStatus(photoIds, "failed");
    }
  }

  private async updatePhotosStatus(
    photoIds: string[],
    status: string,
  ): Promise<void> {
    if (photoIds.length === 0) return;

    const sql = createDb(this.env);
    try {
      await sql`
        UPDATE photos
        SET status = ${status}
        WHERE id IN ${sql(photoIds)}
      `;
    } catch (error) {
      console.error("Failed to update photos status:", error);
    } finally {
      await sql.end({ timeout: 5 });
    }
  }
}

export async function enqueuePhoto(
  env: Env,
  photoId: string,
  storageUrl: string,
): Promise<void> {
  const id = env.BATCHER.idFromName("global");
  const stub = env.BATCHER.get(id);
  await stub.fetch("http://batcher/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photoId, storageUrl }),
  });
}
