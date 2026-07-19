"""PostgreSQL client for the Cloudflare Worker (pg8000)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import pg8000.native


def _prepare(sql: str, params: tuple[Any, ...]) -> tuple[str, dict[str, Any]]:
    if not params:
        return sql, {}
    parts = sql.split("%s")
    if len(parts) - 1 != len(params):
        raise ValueError(
            f"SQL placeholder count does not match params ({len(parts) - 1} vs {len(params)})"
        )
    bound: dict[str, Any] = {}
    out = parts[0]
    for i, part in enumerate(parts[1:]):
        key = f"p{i}"
        bound[key] = params[i]
        out += f":{key}" + part
    return out, bound


@dataclass
class Db:
    conn: pg8000.native.Connection

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        query, kwargs = _prepare(sql, params)
        rows = self.conn.run(query, **kwargs)
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return rows
        columns = self.conn.columns
        if columns:
            names = [col["name"] if isinstance(col, dict) else col for col in columns]
            return [dict(zip(names, row)) for row in rows]
        return [{"value": row} for row in rows]

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        query, kwargs = _prepare(sql, params)
        self.conn.run(query, **kwargs)

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
