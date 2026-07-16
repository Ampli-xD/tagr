"""
RunPod serverless queue handler for Tagr face inference.

Expected job input:
{
  "images": [{"image_id": "<uuid>", "url": "<presigned-or-internal-url>"}],
  "batch_id": "<uuid>",
  "callback_url": "https://<api-host>/api/v1/internal/inference-callback"
}
"""

import logging
import os
from typing import Any, Dict

import httpx
import runpod

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


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    job_input = job.get("input", {})
    images = job_input.get("images", [])
    batch_id = job_input.get("batch_id")
    callback_url = job_input.get("callback_url")

    if not images:
        return {"error": "Missing required field: images"}
    if not batch_id:
        return {"error": "Missing required field: batch_id"}
    if not callback_url:
        return {"error": "Missing required field: callback_url"}

    get_face_analyzer()
    results = process_images(images)
    callback_payload = format_callback_payload(batch_id, results)
    callback_response = _post_callback(callback_url, callback_payload)

    return {
        "acknowledged": True,
        "batch_id": batch_id,
        "processed_images": len(results),
        "callback_response": callback_response,
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
