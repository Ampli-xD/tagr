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
        
        # Prepare request payload for GPU Inference
        payload = {
            "images": [
                {"image_id": item[0], "url": item[1]}
                for item in batch_items
            ]
        }
        
        # Trigger Inference call asynchronously
        asyncio.create_task(self._send_to_inference(payload))

    async def _send_to_inference(self, payload: dict):
        """
        Calls the inference service and invokes the FastAPI callback with results.
        """
        batch_id = str(os.urandom(16).hex())
        predict_url = f"{INFERENCE_SERVER_URL}/predict"
        
        try:
            # 1. Update photos status to "processing" in DB
            photo_ids = [img["image_id"] for img in payload["images"]]
            self._update_photos_status(photo_ids, "processing")
            
            async with httpx.AsyncClient() as client:
                logger.info(f"Sending payload to inference: {predict_url}")
                response = await client.post(predict_url, json=payload, timeout=30.0)
                
                if response.status_code != 200:
                    logger.error(f"Inference failed with status {response.status_code}: {response.text}")
                    self._update_photos_status(photo_ids, "failed")
                    return
                
                inference_results = response.json()
                logger.info("Successfully received predictions from inference container.")
                
                # Format callback payload matching:
                # { batch_id, results: [ { photo_id, faces: [ { bbox, embedding, confidence } ] } ] }
                callback_results = []
                for res in inference_results.get("results", []):
                    faces_data = []
                    for face in res.get("faces", []):
                        bbox = face.get("bounding_box", {})
                        faces_data.append({
                            "bbox": bbox,
                            "embedding": face.get("embedding", []),
                            "confidence": face.get("confidence", 1.0)
                        })
                    callback_results.append({
                        "photo_id": res.get("image_id"),
                        "faces": faces_data
                    })
                
                callback_payload = {
                    "batch_id": batch_id,
                    "results": callback_results
                }
                
                # 2. Call the internal callback URL
                # In V1 we can also call it directly in-process or via http loop.
                # Let's perform a real HTTP POST request to ensure portability.
                logger.info(f"Sending callback to gateway: {API_CALLBACK_URL}")
                cb_res = await client.post(API_CALLBACK_URL, json=callback_payload, timeout=10.0)
                logger.info(f"Callback response: {cb_res.status_code} {cb_res.text}")
                
        except Exception as e:
            logger.error(f"Error in batch inference runner: {str(e)}")
            # Mark these photos as failed
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
