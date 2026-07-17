"""MinIO / S3-compatible storage with AWS SigV4 signing."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import quote

from workers import fetch

_bucket_ready = False


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


def _signed_headers(
    method: str,
    url: str,
    access_key: str,
    secret_key: str,
    headers: dict[str, str],
    payload_hash: str,
) -> dict[str, str]:
    region = "us-east-1"
    service = "s3"
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    from urllib.parse import urlparse

    parsed = urlparse(url)
    canonical_uri = parsed.path or "/"
    canonical_querystring = parsed.query or ""

    signed_header_names = sorted(k.lower() for k in headers)
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
    signed_headers = ";".join(signed_header_names)

    canonical_request = "\n".join(
        [
            method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    signing_key = _get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    out = dict(headers)
    out["x-amz-date"] = amz_date
    out["Authorization"] = authorization
    return out


async def ensure_bucket(env) -> None:
    global _bucket_ready
    if _bucket_ready:
        return

    url = f"{env.STORAGE_ENDPOINT.rstrip('/')}/{env.STORAGE_BUCKET}"
    headers = _signed_headers(
        "PUT",
        url,
        env.STORAGE_ACCESS_KEY,
        env.STORAGE_SECRET_KEY,
        {"host": url.split("//", 1)[1].split("/", 1)[0]},
        hashlib.sha256(b"").hexdigest(),
    )
    response = await fetch(url, method="PUT", headers=headers)
    if response.status in (200, 409):
        _bucket_ready = True
        await _ensure_public_read(env)
        return

    list_url = f"{env.STORAGE_ENDPOINT.rstrip('/')}/"
    list_headers = _signed_headers(
        "GET",
        list_url,
        env.STORAGE_ACCESS_KEY,
        env.STORAGE_SECRET_KEY,
        {"host": list_url.split("//", 1)[1].split("/", 1)[0]},
        hashlib.sha256(b"").hexdigest(),
    )
    list_response = await fetch(list_url, method="GET", headers=list_headers)
    if list_response.ok:
        text = await list_response.text()
        if f"<Name>{env.STORAGE_BUCKET}</Name>" in text:
            _bucket_ready = True
            await _ensure_public_read(env)


async def _ensure_public_read(env) -> None:
    """Allow anonymous GetObject so the inference service can fetch images by
    plain URL (no presigning). Without this, MinIO returns 403 and face
    detection/enrollment fails. Best-effort: never blocks uploads."""
    import json

    policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{env.STORAGE_BUCKET}/*"],
                }
            ],
        }
    )
    body = policy.encode("utf-8")
    url = f"{env.STORAGE_ENDPOINT.rstrip('/')}/{env.STORAGE_BUCKET}?policy="
    host = url.split("//", 1)[1].split("/", 1)[0]
    try:
        headers = _signed_headers(
            "PUT",
            url,
            env.STORAGE_ACCESS_KEY,
            env.STORAGE_SECRET_KEY,
            {"host": host, "content-type": "application/json"},
            hashlib.sha256(body).hexdigest(),
        )
        await fetch(url, method="PUT", headers=headers, body=body)
    except Exception:
        pass


async def upload_image(env, file_bytes: bytes, filename: str, content_type: str) -> str:
    await ensure_bucket(env)
    key = quote(filename, safe="/-_.~")
    url = f"{env.STORAGE_ENDPOINT.rstrip('/')}/{env.STORAGE_BUCKET}/{key}"
    payload_hash = hashlib.sha256(file_bytes).hexdigest()
    host = url.split("//", 1)[1].split("/", 1)[0]
    headers = _signed_headers(
        "PUT",
        url,
        env.STORAGE_ACCESS_KEY,
        env.STORAGE_SECRET_KEY,
        {"host": host, "content-type": content_type or "application/octet-stream"},
        payload_hash,
    )
    response = await fetch(url, method="PUT", headers=headers, body=file_bytes)
    if not response.ok:
        body = await response.text()
        raise RuntimeError(f"Failed to upload image: {response.status} {body}")
    return filename


def get_image_url(env, filename: str, internal: bool = True) -> str:
    endpoint = env.STORAGE_ENDPOINT if internal else env.STORAGE_PUBLIC_ENDPOINT
    return f"{endpoint.rstrip('/')}/{env.STORAGE_BUCKET}/{filename}"
