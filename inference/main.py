import os
import logging
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import httpx
import cv2
import numpy as np
from insightface.app import FaceAnalysis

# Determine device based on environment variable (cpu/gpu)
INFERENCE_DEVICE = os.getenv("INFERENCE_DEVICE", "cpu").lower()
if INFERENCE_DEVICE == "gpu":
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    ctx_id = 0  # GPU device id 0
else:
    providers = ["CPUExecutionProvider"]
    ctx_id = 0

# Initialize InsightFace model once at startup with selected providers
fa = FaceAnalysis(name='buffalo_l', root='~/.insightface', providers=providers)
fa.prepare(ctx_id=ctx_id)

def _normalize(vec: np.ndarray) -> List[float]:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec.tolist()
    return (vec / norm).tolist()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tagr-inference")

app = FastAPI(title="Tagr Inference Service", root_path=os.getenv("INFERENCE_BASE_PATH", ""))

class ImagePredictionRequest(BaseModel):
    image_id: str
    url: str

class PredictRequest(BaseModel):
    images: List[ImagePredictionRequest]

class FacePrediction(BaseModel):
    bounding_box: dict
    confidence: float
    embedding: List[float]

class ImagePredictionResult(BaseModel):
    image_id: str
    faces: List[FacePrediction]

class PredictResponse(BaseModel):
    results: List[ImagePredictionResult]

@app.get("/")
def read_root():
    return {"message": "Inference server is running"}

@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest):
    results = []

    async with httpx.AsyncClient() as client:
        for img_req in payload.images:
            logger.info(f"Processing image {img_req.image_id} from {img_req.url}")

            # Fetch image from MinIO
            try:
                response = await client.get(img_req.url)
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to fetch image {img_req.image_id}. Status: {response.status_code}"
                    )
                image_data = response.content
                logger.info(f"Successfully downloaded image {img_req.image_id} (size: {len(image_data)} bytes)")
            except Exception as e:
                logger.error(f"Error fetching image: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Network error fetching image from storage: {str(e)}"
                )

            # Decode image using OpenCV
            img_arr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            if img is None:
                raise HTTPException(status_code=400, detail="Unable to decode image")

            # Run InsightFace detection and embedding extraction
            faces_data = fa.get(img)
            faces: List[FacePrediction] = []
            for face in faces_data:
                h, w, _ = img.shape
                bbox = {
                    "ymin": round(face.bbox[1] / h, 4),
                    "xmin": round(face.bbox[0] / w, 4),
                    "ymax": round(face.bbox[3] / h, 4),
                    "xmax": round(face.bbox[2] / w, 4),
                }
                confidence = round(float(face.det_score), 3)
                embedding = _normalize(face.embedding)
                faces.append(FacePrediction(bounding_box=bbox, confidence=confidence, embedding=embedding))

            results.append(ImagePredictionResult(image_id=img_req.image_id, faces=faces))

    return PredictResponse(results=results)
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("INFERENCE_HOST", "0.0.0.0")
    port = int(os.getenv("INFERENCE_PORT", "8001"))
    uvicorn.run(app, host=host, port=port, reload=True)
