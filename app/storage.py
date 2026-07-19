import json
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
    """Storage key for the client-uploaded inference JPEG ({name}.infer.jpg)."""
    key = storage_key.lstrip("/")
    root, _ = os.path.splitext(key)
    return f"{root}.infer.jpg"


def get_inference_image_url(original_key: str) -> str:
    """Public URL for the inference copy (uploaded by the client at presign time)."""
    return get_image_url(inference_key_for(original_key), internal=True)


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
