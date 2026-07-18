import json
import boto3
from botocore.client import Config

from .config import (
    STORAGE_ENDPOINT,
    STORAGE_PUBLIC_ENDPOINT,
    STORAGE_ACCESS_KEY,
    STORAGE_SECRET_KEY,
    STORAGE_BUCKET,
    STORAGE_REGION,
    STORAGE_SIGNATURE_VERSION,
)

# Create a session client (short timeouts so a unreachable storage service cannot
# block API startup indefinitely inside Docker).
s3_client = boto3.client(
    "s3",
    endpoint_url=STORAGE_ENDPOINT,
    aws_access_key_id=STORAGE_ACCESS_KEY,
    aws_secret_access_key=STORAGE_SECRET_KEY,
    config=Config(
        signature_version=STORAGE_SIGNATURE_VERSION,
        connect_timeout=5,
        read_timeout=10,
        retries={"max_attempts": 2},
    ),
    region_name=STORAGE_REGION,
)

def _ensure_public_read() -> None:
    """Allow anonymous GetObject so inference can fetch images by URL."""
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

# Ensure the bucket exists on module import
try:
    existing_buckets = [b["Name"] for b in s3_client.list_buckets().get("Buckets", [])]
    if STORAGE_BUCKET not in existing_buckets:
        s3_client.create_bucket(Bucket=STORAGE_BUCKET)
        print(f"Bucket '{STORAGE_BUCKET}' created successfully.")
    _ensure_public_read()
except Exception as e:
    print(f"Warning: Failed to auto-initialize MinIO bucket: {e}")

def upload_image(file_bytes: bytes, filename: str, content_type: str) -> str:
    """
    Uploads an image to MinIO and returns the storage URL/path representation.
    """
    s3_client.put_object(
        Bucket=STORAGE_BUCKET,
        Key=filename,
        Body=file_bytes,
        ContentType=content_type
    )
    # The URL representation can be just the storage key, or the full internal access URL.
    # We will use the storage key as the database identifier and construct URLs as needed.
    return filename

def get_image_url(filename: str, internal: bool = True) -> str:
    """
    Generates a direct URL to access the image.
    If internal=True, returns the hostname suitable for internal docker communication ('http://storage:9000/...').
    Otherwise, returns localhost format for external clients ('http://localhost:9000/...').
    """
    if internal:
        return f"{STORAGE_ENDPOINT}/{STORAGE_BUCKET}/{filename}"
    return f"{STORAGE_PUBLIC_ENDPOINT.rstrip('/')}/{STORAGE_BUCKET}/{filename}"
