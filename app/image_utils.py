"""Resize uploaded photos into a smaller JPEG copy for RunPod inference."""

import io
import logging

from PIL import Image, ImageOps

from .config import INFERENCE_IMAGE_JPEG_QUALITY, INFERENCE_IMAGE_MAX_WIDTH

logger = logging.getLogger("tagr-image-utils")


def resize_for_inference(image_bytes: bytes) -> bytes:
    """
    Downscale so the longest edge is at most INFERENCE_IMAGE_MAX_WIDTH and
    re-encode as JPEG. Keeps aspect ratio; sufficient for face detection/embeddings.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail(
            (INFERENCE_IMAGE_MAX_WIDTH, INFERENCE_IMAGE_MAX_WIDTH),
            Image.Resampling.LANCZOS,
        )
        out = io.BytesIO()
        img.save(
            out,
            format="JPEG",
            quality=INFERENCE_IMAGE_JPEG_QUALITY,
            optimize=True,
        )
        return out.getvalue()
