"""Workers runtime shims for local Docker / host development."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse


class Response:
    def __init__(self, body: str | bytes = "", status: int = 200, headers: dict[str, str] | None = None):
        self.body = body
        self.status = status
        self.headers = headers or {}

    @classmethod
    def json(cls, data: Any, status: int = 200) -> Response:
        return cls(json.dumps(data), status=status, headers={"Content-Type": "application/json"})


class FetchResponse:
    def __init__(self, response: httpx.Response):
        self._response = response
        self.ok = response.is_success
        self.status = response.status_code

    async def text(self) -> str:
        return self._response.text

    async def json(self) -> Any:
        return self._response.json()


async def fetch(url: str, method: str = "GET", headers: dict[str, str] | None = None, body: str | bytes | None = None):
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.request(method, url, headers=headers, content=body)
    return FetchResponse(response)


class WorkerEntrypoint:
    env: Any


class DurableObject:
    def __init__(self, ctx: Any, env: Any):
        self.ctx = ctx
        self.env = env


class WorkerRequest:
    def __init__(self, request: Request):
        self._request = request
        self.method = request.method
        self.url = str(request.url)
        self.headers = request.headers

    async def text(self) -> str:
        return (await self._request.body()).decode()

    async def arrayBuffer(self) -> bytes:
        return await self._request.body()

    async def json(self) -> Any:
        return await self._request.json()


class StaticAssetsBinding:
    def __init__(self, public_dir: Path):
        self._public_dir = public_dir

    async def fetch(self, request: WorkerRequest) -> Response:
        path = request.url
        if "?" in path:
            path = path.split("?", 1)[0]
        rel = path.split("://", 1)[-1]
        if "/" in rel:
            rel = "/" + rel.split("/", 1)[1]
        else:
            rel = "/"
        if rel == "/":
            rel = "/index.html"
        file_path = (self._public_dir / rel.lstrip("/")).resolve()
        if not str(file_path).startswith(str(self._public_dir.resolve())):
            return Response("Not found", status=404)
        if file_path.is_file():
            return _file_response(file_path)
        index = self._public_dir / "index.html"
        if index.is_file():
            return _file_response(index)
        return Response("Not found", status=404)


def _file_response(path: Path) -> Response:
    content = path.read_bytes()
    media = "application/octet-stream"
    if path.suffix == ".html":
        media = "text/html"
    elif path.suffix == ".css":
        media = "text/css"
    elif path.suffix == ".js":
        media = "application/javascript"
    return Response(content, headers={"Content-Type": media})


class _AlarmStorage:
    def __init__(self, batcher: Any):
        self._batcher = batcher
        self._task: asyncio.Task | None = None

    async def setAlarm(self, when_ms: int) -> None:
        if self._task:
            self._task.cancel()
        delay = max(0.0, (when_ms - int(time.time() * 1000)) / 1000.0)

        async def fire() -> None:
            await asyncio.sleep(delay)
            await self._batcher.alarm()

        self._task = asyncio.create_task(fire())


class BatcherStub:
    def __init__(self, batcher: Any):
        self._batcher = batcher

    async def fetch(self, url: str, method: str = "GET", headers: dict[str, str] | None = None, body: str | None = None):
        payload = json.loads(body or "{}")
        await self._batcher.add_photo(payload["photoId"], payload["storageUrl"])
        return Response.json({"ok": True})


class BatcherBinding:
    def __init__(self, batcher: Any):
        self._batcher = batcher

    def idFromName(self, _name: str) -> BatcherBinding:
        return self

    def get(self, _id: Any) -> BatcherStub:
        return BatcherStub(self._batcher)


def load_env(public_dir: Path) -> SimpleNamespace:
    from batcher import PhotoBatcher

    env = SimpleNamespace()
    dev_vars = Path(".dev.vars")
    if dev_vars.is_file():
        for line in dev_vars.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            setattr(env, key.strip(), value.strip())

    import os

    for key in (
        "DATABASE_URL",
        "JWT_SECRET",
        "STORAGE_ENDPOINT",
        "STORAGE_PUBLIC_ENDPOINT",
        "STORAGE_ACCESS_KEY",
        "STORAGE_SECRET_KEY",
        "STORAGE_BUCKET",
        "INFERENCE_URL",
        "API_CALLBACK_URL",
        "BATCH_SIZE",
        "BATCH_TIMEOUT_MS",
        "SIMILARITY_THRESHOLD",
    ):
        if os.environ.get(key):
            setattr(env, key, os.environ[key])

    ctx = SimpleNamespace(storage=_AlarmStorage(None))
    batcher = PhotoBatcher(ctx, env)
    ctx.storage._batcher = batcher
    env.BATCHER = BatcherBinding(batcher)
    env.ASSETS = StaticAssetsBinding(public_dir)
    return env


def to_starlette(response: Response) -> StarletteResponse:
    body = response.body
    if isinstance(body, str):
        body = body.encode()
    return StarletteResponse(content=body, status_code=response.status, headers=response.headers)
