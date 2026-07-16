"""
FastAPI inference server for local development and RunPod load-balancer endpoints.
"""

import asyncio
import logging
import os
from typing import List, Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from core import format_callback_payload, get_face_analyzer, process_images

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tagr-inference-server")

app = FastAPI(
    title="Tagr Inference Service",
    root_path=os.getenv("INFERENCE_BASE_PATH", ""),
)


class ImagePredictionRequest(BaseModel):
    image_id: str
    url: str


class PredictRequest(BaseModel):
    images: List[ImagePredictionRequest]
    batch_id: Optional[str] = None
    callback_url: Optional[str] = None


class FacePrediction(BaseModel):
    bounding_box: dict
    confidence: float
    embedding: List[float]


class ImagePredictionResult(BaseModel):
    image_id: str
    faces: List[FacePrediction]


class PredictResponse(BaseModel):
    results: List[ImagePredictionResult]
    callback_scheduled: bool = False


@app.on_event("startup")
def startup() -> None:
    get_face_analyzer()


@app.get("/")
def read_root():
    return {"message": "Inference server is running"}


@app.get("/ping")
def health_check():
    return {"status": "healthy"}


async def _deliver_callback(callback_url: str, payload: dict) -> None:
    timeout = float(os.getenv("CALLBACK_TIMEOUT_SECONDS", "30"))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(callback_url, json=payload)
            response.raise_for_status()
            logger.info("Callback delivered to %s (%s)", callback_url, response.status_code)
    except Exception as exc:
        logger.error("Failed to deliver callback to %s: %s", callback_url, exc)


@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest, background_tasks: BackgroundTasks):
    if not payload.images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    image_payload = [
        {"image_id": image.image_id, "url": image.url}
        for image in payload.images
    ]

    try:
        results = await asyncio.to_thread(process_images, image_payload)
    except Exception as exc:
        logger.error("Prediction failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response_results = [
        ImagePredictionResult(
            image_id=result["image_id"],
            faces=[FacePrediction(**face) for face in result["faces"]],
        )
        for result in results
    ]

    callback_scheduled = False
    if payload.callback_url and payload.batch_id:
        callback_payload = format_callback_payload(payload.batch_id, results)
        background_tasks.add_task(_deliver_callback, payload.callback_url, callback_payload)
        callback_scheduled = True
        logger.info(
            "Scheduled callback for batch %s to %s",
            payload.batch_id,
            payload.callback_url,
        )

    return PredictResponse(results=response_results, callback_scheduled=callback_scheduled)
