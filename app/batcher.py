import asyncio
import os
import httpx
import logging
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from .database import SessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tagr-batcher")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
BATCH_TIMEOUT_MS = float(os.getenv("BATCH_TIMEOUT_MS", "50")) / 1000.0  # convert to seconds
INFERENCE_SERVER_URL = os.getenv("INFERENCE_SERVER_URL", "http://inference:8001")
API_CALLBACK_URL = os.getenv("API_CALLBACK_URL", "http://web:8000/api/v1/internal/inference-callback")

class PhotoBatcher:
    def __init__(self):
        self.queue: List[Tuple[str, str]] = []  # list of (photo_id, storage_url)
        self.lock = asyncio.Lock()
        self.flush_task = None
        self.first_item_time = None

    async def add_photo(self, photo_id: str, storage_url: str):
        """
        Adds a photo to the batch queue.
        Triggers flush if batch size is reached.
        """
        async with self.lock:
            self.queue.append((photo_id, storage_url))
            logger.info(f"Added photo {photo_id} to batch. Queue size: {len(self.queue)}")
            
            # Start timer if this is the first item in the batch
            if len(self.queue) == 1:
                self.first_item_time = asyncio.get_event_loop().time()
                # Schedule background timeout check
                asyncio.create_task(self._wait_for_timeout())

            if len(self.queue) >= BATCH_SIZE:
                logger.info("Batch size reached. Triggering flush...")
                asyncio.create_task(self.flush())

    async def _wait_for_timeout(self):
        """
        Waits for BATCH_TIMEOUT_MS and flushes if queue is not empty.
        """
        await asyncio.sleep(BATCH_TIMEOUT_MS)
        async with self.lock:
            if len(self.queue) > 0:
                logger.info("Batch timeout elapsed. Triggering flush...")
                asyncio.create_task(self.flush())

    async def flush(self):
        """
        Flushes the batch by pulling items off the queue and sending to inference server.
        """
        batch_items = []
        async with self.lock:
            if not self.queue:
                return
            batch_items = list(self.queue)
            self.queue.clear()
            self.first_item_time = None

        logger.info(f"Flushing batch of size {len(batch_items)}")
        
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
        
        # Trigger Inference call asynchronously
        asyncio.create_task(self._send_to_inference(payload))

    async def _send_to_inference(self, payload: dict):
        """
        Calls the RunPod-compatible inference service via /runsync.
        The worker processes images and posts results to the API callback URL.
        """
        runsync_url = f"{INFERENCE_SERVER_URL.rstrip('/')}/runsync"
        photo_ids = [img["image_id"] for img in payload["input"]["images"]]
        
        try:
            self._update_photos_status(photo_ids, "processing")
            
            async with httpx.AsyncClient() as client:
                logger.info(f"Sending payload to inference: {runsync_url}")
                response = await client.post(runsync_url, json=payload, timeout=120.0)
                
                if response.status_code != 200:
                    logger.error(f"Inference failed with status {response.status_code}: {response.text}")
                    self._update_photos_status(photo_ids, "failed")
                    return
                
                job_result = response.json()
                output = job_result.get("output", {})
                if job_result.get("error") or output.get("error"):
                    logger.error(f"Inference job failed: {job_result}")
                    self._update_photos_status(photo_ids, "failed")
                    return

                logger.info(
                    "Inference batch complete (batch_id=%s, processed=%s)",
                    output.get("batch_id"),
                    output.get("processed_images"),
                )
                
        except Exception as e:
            logger.error(f"Error in batch inference runner: {str(e)}")
            try:
                self._update_photos_status(photo_ids, "failed")
            except Exception:
                pass

    def _update_photos_status(self, photo_ids: List[str], status: str):
        db = SessionLocal()
        try:
            from .models import Photo
            db.query(Photo).filter(Photo.id.in_(photo_ids)).update({"status": status})
            db.commit()
        except Exception as e:
            logger.error(f"Failed to update photos status: {e}")
        finally:
            db.close()

# Global batcher instance
photo_batcher = PhotoBatcher()
