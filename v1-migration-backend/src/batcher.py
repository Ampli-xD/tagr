"""Photo batching Durable Object + inference dispatch."""

from __future__ import annotations

import json
import uuid

from workers import DurableObject, Response, fetch

from db import create_db


class PhotoBatcher(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.queue: list[dict[str, str]] = []
        self.alarm_scheduled = False

    async def fetch(self, request):
        if request.method != "POST":
            return Response("Method not allowed", status=405)
        body = await request.json()
        await self.add_photo(body["photoId"], body["storageUrl"])
        return Response.json({"ok": True})

    async def add_photo(self, photo_id: str, storage_url: str) -> None:
        self.queue.append({"photoId": photo_id, "storageUrl": storage_url})
        batch_size = int(getattr(self.env, "BATCH_SIZE", None) or "10")

        if len(self.queue) >= batch_size:
            await self.flush()
            return

        if not self.alarm_scheduled:
            self.alarm_scheduled = True
            timeout_ms = float(getattr(self.env, "BATCH_TIMEOUT_MS", None) or "50")
            await self.ctx.storage.setAlarm(int(__import__("time").time() * 1000) + int(timeout_ms))

    async def alarm(self) -> None:
        self.alarm_scheduled = False
        if self.queue:
            await self.flush()

    async def flush(self) -> None:
        batch_items = list(self.queue)
        self.queue = []
        self.alarm_scheduled = False
        if not batch_items:
            return

        photo_ids = [item["photoId"] for item in batch_items]
        await self.update_photos_status(photo_ids, "processing")

        batch_id = str(uuid.uuid4())
        runsync_url = f"{self.env.INFERENCE_URL.rstrip('/')}/runsync"
        payload = {
            "input": {
                "images": [
                    {"image_id": item["photoId"], "url": item["storageUrl"]}
                    for item in batch_items
                ],
                "batch_id": batch_id,
                "callback_url": self.env.API_CALLBACK_URL,
            }
        }

        try:
            response = await fetch(
                runsync_url,
                method="POST",
                headers={"Content-Type": "application/json"},
                body=json.dumps(payload),
            )
            if not response.ok:
                text = await response.text()
                print(f"Inference failed: {response.status} {text}")
                await self.update_photos_status(photo_ids, "failed")
                return

            job_result = await response.json()
            output = job_result.get("output", {})
            if job_result.get("error") or output.get("error"):
                print(f"Inference job failed: {job_result}")
                await self.update_photos_status(photo_ids, "failed")
                return

            print(
                f"Inference batch complete (batch_id={output.get('batch_id')}, "
                f"processed={output.get('processed_images')})"
            )
        except Exception as exc:
            print(f"Error in batch inference runner: {exc}")
            await self.update_photos_status(photo_ids, "failed")

    async def update_photos_status(self, photo_ids: list[str], status: str) -> None:
        if not photo_ids:
            return
        db = create_db(self.env.DATABASE_URL)
        try:
            placeholders = ", ".join(f"'{pid}'::uuid" for pid in photo_ids)
            db.execute(f"UPDATE photos SET status = %s WHERE id IN ({placeholders})", (status,))
        except Exception as exc:
            print(f"Failed to update photos status: {exc}")
        finally:
            db.close()


async def enqueue_photo(env, photo_id: str, storage_url: str) -> None:
    stub = env.BATCHER.get(env.BATCHER.idFromName("global"))
    await stub.fetch(
        "http://batcher/add",
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"photoId": photo_id, "storageUrl": storage_url}),
    )
