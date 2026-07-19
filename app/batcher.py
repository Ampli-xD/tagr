import asyncio
import httpx
import logging
import os
import uuid
from typing import List, Tuple
from sqlalchemy.orm import Session
from .database import SessionLocal
from .config import (
    BATCH_SIZE,
    BATCH_TIMEOUT_MS as _BATCH_TIMEOUT_MS,
    INFERENCE_SERVER_URL,
    INFERENCE_BATCH_TIMEOUT_SECONDS,
    API_CALLBACK_URL,
    inference_request_headers,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tagr-batcher")

BATCH_TIMEOUT_MS = _BATCH_TIMEOUT_MS / 1000.0


class PhotoBatcher:
    def __init__(self):
        self.queue: List[Tuple[str, str]] = []
        self.lock = asyncio.Lock()
        self._flush_in_progress = False
        self.first_item_time = None

    async def add_photo(self, photo_id: str, storage_url: str):
        async with self.lock:
            self.queue.append((photo_id, storage_url))
            logger.info("Added photo %s to batch. Queue size: %s", photo_id, len(self.queue))

            if len(self.queue) == 1:
                self.first_item_time = asyncio.get_event_loop().time()
                asyncio.create_task(self._wait_for_timeout())

            if len(self.queue) >= BATCH_SIZE:
                asyncio.create_task(self.flush())

    async def _wait_for_timeout(self):
        await asyncio.sleep(BATCH_TIMEOUT_MS)
        async with self.lock:
            if self.queue:
                asyncio.create_task(self.flush())

    async def flush(self):
        async with self.lock:
            if not self.queue or self._flush_in_progress:
                return
            batch_items = self.queue[:BATCH_SIZE]
            self.queue = self.queue[BATCH_SIZE:]
            self._flush_in_progress = True
            if not self.queue:
                self.first_item_time = None

        if not batch_items:
            async with self.lock:
                self._flush_in_progress = False
            return

        logger.info("Flushing batch of size %s (%s remaining in queue)", len(batch_items), len(self.queue))

        batch_id = os.urandom(16).hex()
        payload = {
            "input": {
                "images": [
                    {"image_id": item[0], "url": item[1]}
                    for item in batch_items
                ],
                "batch_id": batch_id,
                "callback_url": API_CALLBACK_URL,
            }
        }

        try:
            await self._send_to_inference(payload)
        finally:
            async with self.lock:
                self._flush_in_progress = False
                if len(self.queue) >= BATCH_SIZE:
                    asyncio.create_task(self.flush())

    async def _send_to_inference(self, payload: dict):
        runsync_url = f"{INFERENCE_SERVER_URL.rstrip('/')}/runsync"
        photo_ids = [img["image_id"] for img in payload["input"]["images"]]

        try:
            self._update_photos_status(photo_ids, "processing")

            async with httpx.AsyncClient() as client:
                logger.info("Sending batch of %s to %s", len(photo_ids), runsync_url)
                response = await client.post(
                    runsync_url,
                    json=payload,
                    headers=inference_request_headers(),
                    timeout=INFERENCE_BATCH_TIMEOUT_SECONDS,
                )

                if response.status_code != 200:
                    if response.status_code == 401:
                        logger.error(
                            "RunPod 401 Unauthorized — set RUNPOD_API_KEY on Render "
                            "(RunPod dashboard → Settings → API Keys). Response: %s",
                            response.text,
                        )
                    else:
                        logger.error("Inference HTTP %s: %s", response.status_code, response.text)
                    self._update_photos_status(photo_ids, "failed")
                    return

                job_result = response.json()
                output = job_result.get("output", {})
                top_error = job_result.get("error") or output.get("error")
                if top_error:
                    logger.error("Inference job failed: %s", job_result)
                    failed_ids = [
                        str(item.get("photo_id"))
                        for item in output.get("errors", [])
                        if item.get("photo_id")
                    ]
                    if failed_ids:
                        self._update_photos_status(failed_ids, "failed")
                        succeeded = [pid for pid in photo_ids if pid not in failed_ids]
                        if not succeeded:
                            return
                    else:
                        self._update_photos_status(photo_ids, "failed")
                        return

                logger.info(
                    "Inference batch accepted (batch_id=%s, processed=%s, errors=%s)",
                    output.get("batch_id"),
                    output.get("processed_images"),
                    len(output.get("errors", [])),
                )

        except Exception as e:
            logger.error("Error in batch inference runner: %s", e)
            self._update_photos_status(photo_ids, "failed")

    def _update_photos_status(self, photo_ids: List[str], status: str):
        db = SessionLocal()
        try:
            from .models import Photo
            ids = [uuid.UUID(pid) for pid in photo_ids]
            db.query(Photo).filter(Photo.id.in_(ids)).update({"status": status}, synchronize_session=False)
            db.commit()
        except Exception as e:
            logger.error("Failed to update photos status: %s", e)
        finally:
            db.close()


photo_batcher = PhotoBatcher()
