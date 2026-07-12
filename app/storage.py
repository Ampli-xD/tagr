import os
import boto3
from botocore.client import Config

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT", "http://storage:9000")
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "minioadmin")
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "minioadmin")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "tagr-bucket")

# Create a session client
s3_client = boto3.client(
    "s3",
    endpoint_url=STORAGE_ENDPOINT,
    aws_access_key_id=STORAGE_ACCESS_KEY,
    aws_secret_access_key=STORAGE_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1"
)

# Ensure the bucket exists on module import
try:
    existing_buckets = [b["Name"] for b in s3_client.list_buckets().get("Buckets", [])]
    if STORAGE_BUCKET not in existing_buckets:
        s3_client.create_bucket(Bucket=STORAGE_BUCKET)
        print(f"Bucket '{STORAGE_BUCKET}' created successfully.")
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
    else:
        # Swap out internal docker service name 'storage' with localhost for host machine access
        external_endpoint = STORAGE_ENDPOINT.replace("http://storage:", "http://localhost:")
        return f"{external_endpoint}/{STORAGE_BUCKET}/{filename}"
