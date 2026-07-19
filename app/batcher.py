import asyncio
import httpx
import logging
import os
import uuid
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from .database import SessionLocal
from .config import (
    BATCH_SIZE,
    BATCH_TIMEOUT_MS as _BATCH_TIMEOUT_MS,
    INFERENCE_SERVER_URL,
    INFERENCE_BATCH_TIMEOUT_SECONDS,
    inference_request_headers,
    inference_runsync_url,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tagr-batcher")

BATCH_TIMEOUT_SEC = _BATCH_TIMEOUT_MS / 1000.0


class PhotoBatcher:
    def __init__(self):
        self.queue: List[Tuple[str, str]] = []
        self.lock = asyncio.Lock()
        self._flush_in_progress = False
        self._flush_timer_task: Optional[asyncio.Task] = None

    def _cancel_flush_timer(self) -> None:
        if self._flush_timer_task and not self._flush_timer_task.done():
            self._flush_timer_task.cancel()
        self._flush_timer_task = None

    def _schedule_flush_timer(self) -> None:
        """Flush partial queue after BATCH_TIMEOUT_MS if batch is not full yet."""
        if self._flush_timer_task and not self._flush_timer_task.done():
            return
        self._flush_timer_task = asyncio.create_task(self._wait_and_flush())

    async def _wait_and_flush(self) -> None:
        try:
            await asyncio.sleep(BATCH_TIMEOUT_SEC)
        except asyncio.CancelledError:
            return
        await self.flush()

    async def add_photo(self, photo_id: str, storage_url: str):
        async with self.lock:
            self.queue.append((photo_id, storage_url))
            logger.info(
                "Added photo %s to batch. Queue size: %s (flush at %s or after %.1fs)",
                photo_id,
                len(self.queue),
                BATCH_SIZE,
                BATCH_TIMEOUT_SEC,
            )

            if len(self.queue) >= BATCH_SIZE:
                self._cancel_flush_timer()
                asyncio.create_task(self.flush())
            else:
                self._schedule_flush_timer()

    async def flush(self):
        async with self.lock:
            if not self.queue:
                return
            if self._flush_in_progress:
                self._cancel_flush_timer()
                self._schedule_flush_timer()
                return
            batch_items = self.queue[:BATCH_SIZE]
            self.queue = self.queue[BATCH_SIZE:]
            self._flush_in_progress = True
            self._cancel_flush_timer()

        if not batch_items:
            async with self.lock:
                self._flush_in_progress = False
            return

        logger.info(
            "Flushing batch of size %s (%s remaining in queue)",
            len(batch_items),
            len(self.queue),
        )

        batch_id = os.urandom(16).hex()
        payload = {
            "input": {
                "images": [
                    {"image_id": item[0], "url": item[1]}
                    for item in batch_items
                ],
                "batch_id": batch_id,
            }
        }

        try:
            await self._send_to_inference(payload, batch_id)
        finally:
            async with self.lock:
                self._flush_in_progress = False
                if len(self.queue) >= BATCH_SIZE:
                    asyncio.create_task(self.flush())
                elif self.queue:
                    self._schedule_flush_timer()

    async def _send_to_inference(self, payload: dict, batch_id: str):
        from .internal import normalize_sync_inference_output, process_inference_callback

        runsync_url = inference_runsync_url()
        photo_ids = [img["image_id"] for img in payload["input"]["images"]]

        try:
            self._update_photos_status(photo_ids, "processing")

            async with httpx.AsyncClient() as client:
                logger.info("Sending batch of %s to %s", len(photo_ids), runsync_url)
                response = await client.post(
                    runsync_url,
                    json=payload,
                    headers=inference_request_headers(),
                    timeout=INFERENCE_BATCH_TIMEOUT_SECONDS + 30,
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
                status = job_result.get("status", "")
                output = job_result.get("output") or {}
                if not isinstance(output, dict):
                    output = {}

                top_error = job_result.get("error") or output.get("error")
                if status == "IN_PROGRESS":
                    logger.warning(
                        "RunPod runsync returned IN_PROGRESS (job still running). "
                        "Response: %s",
                        job_result,
                    )
                    self._update_photos_status(photo_ids, "pending")
                    return

                if top_error:
                    logger.error("Inference job failed: %s", job_result)
                    failed_ids = [
                        str(item.get("photo_id"))
                        for item in output.get("errors", [])
                        if item.get("photo_id")
                    ]
                    if failed_ids:
                        self._update_photos_status(failed_ids, "failed")
                    else:
                        self._update_photos_status(photo_ids, "failed")
                    return

                # Legacy path: worker posted callback itself during runsync.
                if output.get("acknowledged"):
                    logger.info(
                        "Inference batch accepted via worker callback (batch_id=%s, processed=%s)",
                        output.get("batch_id"),
                        output.get("processed_images"),
                    )
                    return

                if status == "COMPLETED" or output.get("results") is not None:
                    callback_payload = normalize_sync_inference_output(batch_id, output)
                    asyncio.create_task(
                        asyncio.to_thread(process_inference_callback, callback_payload)
                    )
                    logger.info(
                        "Inference batch completed (batch_id=%s, results=%s, errors=%s, status=%s)",
                        batch_id,
                        len(callback_payload.get("results", [])),
                        len(callback_payload.get("errors", [])),
                        status,
                    )
                    return

                logger.error("Unexpected RunPod response: %s", job_result)
                self._update_photos_status(photo_ids, "failed")

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
