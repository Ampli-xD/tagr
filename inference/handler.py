"""
RunPod serverless handler for Tagr face inference.

Batch input (with callback):
{
  "images": [{"image_id": "<uuid>", "url": "<url>"}],
  "batch_id": "<uuid>",
  "callback_url": "https://<api>/api/v1/internal/inference-callback"
}

Sync input (enrollment / direct predict):
{
  "images": [{"image_id": "<uuid>", "url": "<url>"}]
}
"""

import logging
import os
from typing import Any, Dict, List

import httpx

from core import format_callback_payload, get_face_analyzer, process_images

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tagr-inference-handler")

CALLBACK_TIMEOUT_SECONDS = float(os.getenv("CALLBACK_TIMEOUT_SECONDS", "30"))


def _post_callback(callback_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Posting inference callback to %s", callback_url)
    with httpx.Client(timeout=CALLBACK_TIMEOUT_SECONDS) as client:
        response = client.post(callback_url, json=payload)
        response.raise_for_status()
        return response.json()


def _format_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "image_id": result["image_id"],
            "faces": result["faces"],
        }
        for result in results
    ]


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    job_input = job.get("input", {})
    images = job_input.get("images", [])
    batch_id = job_input.get("batch_id")
    callback_url = job_input.get("callback_url")

    if not images:
        return {"error": "Missing required field: images"}

    get_face_analyzer()

    try:
        results = process_images(images)
    except Exception as exc:
        logger.error("Inference failed: %s", exc)
        return {"error": str(exc)}

    if callback_url and batch_id:
        callback_payload = format_callback_payload(batch_id, results)
        try:
            callback_response = _post_callback(callback_url, callback_payload)
        except Exception as exc:
            logger.error("Callback failed: %s", exc)
            return {"error": f"Callback failed: {exc}"}

        return {
            "acknowledged": True,
            "batch_id": batch_id,
            "processed_images": len(results),
            "callback_response": callback_response,
        }

    return {"results": _format_results(results)}
