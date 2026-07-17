"""Tagr API — Cloudflare Worker entrypoint (Python)."""

from __future__ import annotations

from urllib.parse import urlparse

from auth_util import get_user_id_from_token
from batcher import PhotoBatcher
from db import create_db
from http_util import json_response, options_response
from routes import auth, internal, photos, social
from workers import Response, WorkerEntrypoint


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        if request.method == "OPTIONS":
            return options_response()

        url = urlparse(request.url)
        path = url.path

        if path == "/api/v1/docs":
            return Response("", status=302, headers={"Location": "/api/v1/health"})

        if path.startswith("/api/v1/"):
            return await self.handle_api(request, path[len("/api/v1/") :])

        return await self.env.ASSETS.fetch(request)

    async def handle_api(self, request, subpath: str):
        method = request.method
        user_id = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                user_id = get_user_id_from_token(auth_header[7:], self.env.JWT_SECRET)
            except Exception:
                user_id = None

        if subpath == "health" and method == "GET":
            return await self.health()

        if subpath.startswith("auth/"):
            return await auth.handle_auth(self.env, method, subpath[5:], request, user_id)

        if subpath.startswith("photos/"):
            return await photos.handle_photos(self.env, method, subpath[7:], request, user_id)

        if subpath.startswith("internal/"):
            return await internal.handle_internal(self.env, method, subpath[9:], request, user_id)

        return await social.handle_social(self.env, method, subpath, request, user_id)

    async def health(self):
        db = create_db(self.env.DATABASE_URL)
        try:
            db.fetchone("SELECT 1")
            return json_response({"status": "ok", "service": "tagr-api-worker"})
        except Exception as exc:
            return json_response(
                {
                    "status": "degraded",
                    "service": "tagr-api-worker",
                    "database": str(exc),
                },
                503,
            )
        finally:
            db.close()
