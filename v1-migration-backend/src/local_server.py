"""Local ASGI server for Docker / host dev.

Python Workers (pywrangler) run inside Pyodide and cannot open TCP sockets to
Postgres. This server reuses the same route handlers with native pg8000 access.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
APP_DIR = SRC_DIR.parent
PUBLIC_DIR = APP_DIR / "public"
sys.path.insert(0, str(SRC_DIR))

import local_workers as workers_shim

sys.modules["workers"] = workers_shim

from entry import Default  # noqa: E402
from local_workers import WorkerRequest, load_env, to_starlette  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.routing import Route  # noqa: E402

ENV = load_env(PUBLIC_DIR)
WORKER = Default.__new__(Default)
WORKER.env = ENV


async def handle(request: Request):
    worker_request = WorkerRequest(request)
    response = await WORKER.fetch(worker_request)
    return to_starlette(response)


app = Starlette(
    routes=[
        Route("/{path:path}", handle, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]),
        Route("/", handle, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]),
    ]
)


def main() -> None:
    import os
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8787"))
    uvicorn.run("local_server:app", host=host, port=port, factory=False)


if __name__ == "__main__":
    main()
