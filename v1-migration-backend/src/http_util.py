"""HTTP helpers: JSON responses, CORS, multipart parsing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from workers import Response


def cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Credentials": "true",
    }


def json_response(data: Any, status: int = 200) -> Response:
    headers = {"Content-Type": "application/json", **cors_headers()}
    return Response(json.dumps(data), status=status, headers=headers)


def options_response() -> Response:
    return Response("", status=204, headers=cors_headers())


@dataclass
class UploadedFile:
    name: str
    content_type: str
    data: bytes


async def parse_json(request) -> dict[str, Any]:
    text = await request.text()
    if not text:
        return {}
    return json.loads(text)


def parse_query(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return {k: v[0] for k, v in qs.items()}


async def parse_multipart(request) -> tuple[dict[str, str], dict[str, UploadedFile]]:
    content_type = request.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        return {}, {}

    boundary_match = re.search(r"boundary=(.+)", content_type)
    if not boundary_match:
        return {}, {}

    boundary = boundary_match.group(1).strip().strip('"')
    body = await request.arrayBuffer()
    if hasattr(body, "tobytes"):
        raw = body.tobytes()
    else:
        raw = bytes(body)

    fields: dict[str, str] = {}
    files: dict[str, UploadedFile] = {}

    delimiter = b"--" + boundary.encode()
    for part in raw.split(delimiter):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        header_blob, _, content = part.partition(b"\r\n\r\n")
        if not header_blob:
            continue
        headers_text = header_blob.decode("utf-8", errors="replace")
        name_match = re.search(r'name="([^"]+)"', headers_text)
        if not name_match:
            continue
        name = name_match.group(1)
        content = content.rstrip(b"\r\n")

        filename_match = re.search(r'filename="([^"]*)"', headers_text)
        if filename_match:
            ctype_match = re.search(r"Content-Type:\s*(\S+)", headers_text, re.I)
            files[name] = UploadedFile(
                name=filename_match.group(1) or name,
                content_type=ctype_match.group(1) if ctype_match else "application/octet-stream",
                data=content,
            )
        else:
            fields[name] = content.decode("utf-8", errors="replace")

    return fields, files


def form_field(fields: dict[str, str], key: str) -> str:
    value = fields.get(key, "").strip()
    if not value:
        raise ValueError(f"Missing field: {key}")
    return value
