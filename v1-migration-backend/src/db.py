"""PostgreSQL client for the Cloudflare Worker (pg8000)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import pg8000.native


@dataclass
class Db:
    conn: pg8000.native.Connection

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        rows = self.conn.run(sql, *params)
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return rows
        return [{"value": row} for row in rows]

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.conn.run(sql, *params)

    def close(self) -> None:
        self.conn.close()


def create_db(database_url: str) -> Db:
    parsed = urlparse(database_url)
    conn = pg8000.native.Connection(
        user=parsed.username or "postgres",
        password=parsed.password or "",
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        database=(parsed.path or "/tagr_db").lstrip("/"),
    )
    return Db(conn)


def embedding_literal(embedding: list[float]) -> str:
    return json.dumps(embedding)
