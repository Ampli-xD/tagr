"""
Download and vendor the InsightFace model used by the inference service.

The model is fetched ONCE (at Docker build time, or manually for local dev) into
``inference/assets/models/buffalo_l`` so that it is never downloaded again at
runtime / on every container start.

Only the detection (``det_10g``) and recognition (``w600k_r50``) sub-models are
kept, since those are the only ones the inference code uses (bounding box +
512-d embedding). See ``core.py``.

Usage:
    python download_model.py            # downloads into ./assets/models/buffalo_l
    INSIGHTFACE_ROOT=/somewhere python download_model.py
"""

import io
import os
import sys
import urllib.request
import zipfile

MODEL_NAME = "buffalo_l"
MODEL_URL = os.getenv(
    "BUFFALO_L_URL",
    "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
)
# Only the files the inference pipeline actually loads.
KEEP_FILES = {"det_10g.onnx", "w600k_r50.onnx"}

ASSETS_ROOT = os.getenv(
    "INSIGHTFACE_ROOT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"),
)
TARGET_DIR = os.path.join(ASSETS_ROOT, "models", MODEL_NAME)


def _already_present() -> bool:
    return all(os.path.isfile(os.path.join(TARGET_DIR, f)) for f in KEEP_FILES)


def main() -> int:
    if _already_present():
        print(f"Model already present in {TARGET_DIR}; skipping download.")
        return 0

    os.makedirs(TARGET_DIR, exist_ok=True)
    print(f"Downloading {MODEL_NAME} from {MODEL_URL} ...")
    with urllib.request.urlopen(MODEL_URL) as resp:  # noqa: S310 (trusted URL)
        data = resp.read()
    print(f"Downloaded {len(data) / (1024 * 1024):.1f} MB; extracting required models ...")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            base = os.path.basename(name)
            if base in KEEP_FILES:
                dest = os.path.join(TARGET_DIR, base)
                with zf.open(name) as src, open(dest, "wb") as out:
                    out.write(src.read())
                print(f"  -> {dest}")

    if not _already_present():
        print("ERROR: expected model files were not found in the archive.", file=sys.stderr)
        return 1

    print(f"Model ready in {TARGET_DIR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
