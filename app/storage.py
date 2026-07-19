import json
import logging
import os

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import (
    STORAGE_ENDPOINT,
    STORAGE_INFERENCE_ENDPOINT,
    STORAGE_PUBLIC_ENDPOINT,
    STORAGE_ACCESS_KEY,
    STORAGE_SECRET_KEY,
    STORAGE_BUCKET,
    STORAGE_REGION,
    STORAGE_SIGNATURE_VERSION,
    PRESIGNED_UPLOAD_EXPIRES_SECONDS,
)

logger = logging.getLogger("tagr-storage")


def _is_remote_storage() -> bool:
    return any(
        host in STORAGE_ENDPOINT
        for host in ("supabase.co", "amazonaws.com", "r2.cloudflarestorage.com")
    )


def _is_supabase_storage() -> bool:
    return "supabase.co" in STORAGE_ENDPOINT


def _s3_client():
    kwargs = {
        "endpoint_url": STORAGE_ENDPOINT,
        "aws_access_key_id": STORAGE_ACCESS_KEY,
        "aws_secret_access_key": STORAGE_SECRET_KEY,
        "config": Config(
            signature_version=STORAGE_SIGNATURE_VERSION,
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2},
        ),
        "region_name": STORAGE_REGION,
    }
    return boto3.client("s3", **kwargs)


s3_client = _s3_client()


def _ensure_public_read() -> None:
    """Allow anonymous GetObject so inference can fetch images by URL (MinIO only)."""
    policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{STORAGE_BUCKET}/*"],
                }
            ],
        }
    )
    try:
        s3_client.put_bucket_policy(Bucket=STORAGE_BUCKET, Policy=policy)
    except Exception as exc:
        print(f"Warning: Failed to set public-read bucket policy: {exc}")


def _ensure_local_bucket() -> None:
    try:
        existing_buckets = [b["Name"] for b in s3_client.list_buckets().get("Buckets", [])]
        if STORAGE_BUCKET not in existing_buckets:
            s3_client.create_bucket(Bucket=STORAGE_BUCKET)
            print(f"Bucket '{STORAGE_BUCKET}' created successfully.")
        _ensure_public_read()
    except Exception as exc:
        print(f"Warning: Failed to auto-initialize local storage bucket: {exc}")


if _is_remote_storage():
    print(f"Using remote object storage at {STORAGE_ENDPOINT}")
else:
    _ensure_local_bucket()


def upload_image(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload an image and return the storage key (path inside the bucket)."""
    s3_client.put_object(
        Bucket=STORAGE_BUCKET,
        Key=filename,
        Body=file_bytes,
        ContentType=content_type,
    )
    return filename


def create_presigned_upload_url(
    filename: str,
    content_type: str,
    expires_in: int | None = None,
) -> str:
    """
    Return a short-lived PUT URL so the browser can upload directly to object storage.
    Works with Supabase Storage (S3-compatible) and MinIO.
    """
    expiry = expires_in if expires_in is not None else PRESIGNED_UPLOAD_EXPIRES_SECONDS
    return s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": STORAGE_BUCKET,
            "Key": filename,
            "ContentType": content_type,
        },
        ExpiresIn=expiry,
    )


def object_exists(filename: str) -> bool:
    """Check whether an object key exists in the bucket."""
    try:
        s3_client.head_object(Bucket=STORAGE_BUCKET, Key=filename.lstrip("/"))
        return True
    except ClientError:
        return False


def inference_key_for(storage_key: str) -> str:
    """Derive the storage key for the inference-sized JPEG copy of an original."""
    key = storage_key.lstrip("/")
    root, _ = os.path.splitext(key)
    return f"{root}.infer.jpg"


def download_object(filename: str) -> bytes:
    """Download an object from storage."""
    response = s3_client.get_object(Bucket=STORAGE_BUCKET, Key=filename.lstrip("/"))
    return response["Body"].read()


def ensure_inference_copy(original_key: str) -> str:
    """
    Ensure a downscaled JPEG copy exists for RunPod. Original gallery key is unchanged.
    Falls back to the original key if resize/upload fails.
    """
    infer_key = inference_key_for(original_key)
    if object_exists(infer_key):
        return infer_key
    try:
        from .image_utils import resize_for_inference

        original_bytes = download_object(original_key)
        infer_bytes = resize_for_inference(original_bytes)
        upload_image(infer_bytes, infer_key, "image/jpeg")
        logger.info(
            "Created inference copy %s (%s KB) from %s",
            infer_key,
            len(infer_bytes) // 1024,
            original_key,
        )
        return infer_key
    except Exception as exc:
        logger.warning(
            "Could not create inference copy for %s, using original: %s",
            original_key,
            exc,
        )
        return original_key


def get_inference_image_url(original_key: str) -> str:
    """Public URL for the inference-sized copy (created on demand if missing)."""
    infer_key = ensure_inference_copy(original_key)
    return get_image_url(infer_key, internal=True)


def get_image_url(filename: str, internal: bool = True) -> str:
    """
    Build a URL to fetch an object.

    Supabase public buckets: HTTPS object URL works for browsers and inference.
    MinIO: path-style endpoint URL; inference may need STORAGE_INFERENCE_ENDPOINT.
    """
    key = filename.lstrip("/")

    if _is_supabase_storage():
        base = STORAGE_PUBLIC_ENDPOINT.rstrip("/")
        return f"{base}/{key}"

    if internal:
        endpoint = (STORAGE_INFERENCE_ENDPOINT or STORAGE_ENDPOINT).rstrip("/")
        return f"{endpoint}/{STORAGE_BUCKET}/{key}"

    endpoint = STORAGE_PUBLIC_ENDPOINT.rstrip("/")
    return f"{endpoint}/{STORAGE_BUCKET}/{key}"
