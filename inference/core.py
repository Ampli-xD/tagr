import logging
import os
from typing import Any, Dict, List, Optional

import cv2
import httpx
import numpy as np
from insightface.app import FaceAnalysis

logger = logging.getLogger("tagr-inference")

_face_analyzer: Optional[FaceAnalysis] = None


def _resolve_providers() -> tuple[list[str], int]:
    device = os.getenv("INFERENCE_DEVICE", "cpu").lower()
    if device == "gpu":
        return ["CUDAExecutionProvider", "CPUExecutionProvider"], 0
    return ["CPUExecutionProvider"], 0


def get_face_analyzer() -> FaceAnalysis:
    global _face_analyzer
    if _face_analyzer is None:
        providers, ctx_id = _resolve_providers()
        logger.info("Initializing InsightFace buffalo_l (providers=%s)", providers)
        analyzer = FaceAnalysis(name="buffalo_l", root="~/.insightface", providers=providers)
        analyzer.prepare(ctx_id=ctx_id)
        _face_analyzer = analyzer
    return _face_analyzer


def normalize_embedding(vec: np.ndarray) -> List[float]:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec.tolist()
    return (vec / norm).tolist()


def extract_faces_from_bytes(image_data: bytes) -> List[Dict[str, Any]]:
    img_arr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Unable to decode image")

    faces_data = get_face_analyzer().get(img)
    h, w, _ = img.shape
    faces: List[Dict[str, Any]] = []

    for face in faces_data:
        faces.append(
            {
                "bounding_box": {
                    "ymin": round(face.bbox[1] / h, 4),
                    "xmin": round(face.bbox[0] / w, 4),
                    "ymax": round(face.bbox[3] / h, 4),
                    "xmax": round(face.bbox[2] / w, 4),
                },
                "confidence": round(float(face.det_score), 3),
                "embedding": normalize_embedding(face.embedding),
            }
        )

    return faces


def process_images(images: List[Dict[str, str]], timeout: float = 60.0) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    with httpx.Client(timeout=timeout) as client:
        for image in images:
            image_id = image["image_id"]
            url = image["url"]
            logger.info("Processing image %s from %s", image_id, url)

            response = client.get(url)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to fetch image {image_id}. Status: {response.status_code}"
                )

            logger.info(
                "Downloaded image %s (%s bytes)",
                image_id,
                len(response.content),
            )
            faces = extract_faces_from_bytes(response.content)
            results.append({"image_id": image_id, "faces": faces})

    return results


def format_callback_payload(batch_id: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    callback_results = []
    for result in results:
        faces_data = []
        for face in result.get("faces", []):
            faces_data.append(
                {
                    "bbox": face.get("bounding_box", {}),
                    "embedding": face.get("embedding", []),
                    "confidence": face.get("confidence", 1.0),
                }
            )
        callback_results.append(
            {
                "photo_id": result.get("image_id"),
                "faces": faces_data,
            }
        )

    return {
        "batch_id": batch_id,
        "results": callback_results,
    }
