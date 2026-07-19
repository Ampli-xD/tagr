import logging
import os
from typing import Any, Dict, List, Optional

import cv2
import httpx
import numpy as np
from insightface.app import FaceAnalysis

logger = logging.getLogger("tagr-inference")

_face_analyzer: Optional[FaceAnalysis] = None

MODEL_NAME = "buffalo_l"

# Ship the model with the code so it is never downloaded at runtime. InsightFace
# resolves models at "<root>/models/<name>", so the ONNX files live in
# inference/assets/models/buffalo_l. Overridable via INSIGHTFACE_ROOT.
INSIGHTFACE_ROOT = os.getenv(
    "INSIGHTFACE_ROOT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"),
)

# Only the detection + recognition models are bundled/used: detection provides
# the bounding box + score, recognition provides the 512-d embedding. The other
# buffalo_l sub-models (landmarks, gender/age) are not needed here.
ALLOWED_MODULES = ["detection", "recognition"]


def _resolve_providers() -> tuple[list[str], int]:
    device = os.getenv("INFERENCE_DEVICE", "cpu").lower()
    if device == "gpu":
        return ["CUDAExecutionProvider", "CPUExecutionProvider"], 0
    return ["CPUExecutionProvider"], 0


def get_face_analyzer() -> FaceAnalysis:
    global _face_analyzer
    if _face_analyzer is None:
        providers, ctx_id = _resolve_providers()
        model_dir = os.path.join(INSIGHTFACE_ROOT, "models", MODEL_NAME)
        if not os.path.isdir(model_dir):
            logger.warning(
                "Bundled model dir %s not found; InsightFace may attempt a download.",
                model_dir,
            )
        logger.info(
            "Initializing InsightFace %s from %s (providers=%s)",
            MODEL_NAME, model_dir, providers,
        )
        analyzer = FaceAnalysis(
            name=MODEL_NAME,
            root=INSIGHTFACE_ROOT,
            allowed_modules=ALLOWED_MODULES,
            providers=providers,
        )
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


def process_images(
    images: List[Dict[str, str]], timeout: float = 60.0
) -> tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Process each image; skip failures so one bad URL does not fail the batch."""
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    with httpx.Client(timeout=timeout) as client:
        for image in images:
            image_id = image["image_id"]
            url = image["url"]
            try:
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
            except Exception as exc:
                logger.error("Skipping image %s: %s", image_id, exc)
                errors.append({"photo_id": image_id, "error": str(exc)})

    return results, errors


def format_callback_payload(
    batch_id: str,
    results: List[Dict[str, Any]],
    errors: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
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

    payload = {
        "batch_id": batch_id,
        "results": callback_results,
    }
    if errors:
        payload["errors"] = errors
    return payload
