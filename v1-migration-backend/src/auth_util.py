"""JWT helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt


def create_access_token(user_id: str, jwt_secret: str, days: int = 7) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    return jwt.encode(
        {"user_id": user_id, "exp": expire},
        jwt_secret,
        algorithm="HS256",
    )


def get_user_id_from_token(token: str, jwt_secret: str) -> str:
    payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    user_id = payload.get("user_id")
    if not user_id:
        raise ValueError("Invalid token payload")
    return str(user_id)
