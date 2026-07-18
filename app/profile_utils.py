"""User profile helpers: serialization, zodiac, username generation."""

import re
import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import User
from .storage import get_image_url


def compute_zodiac(birthday: date) -> str:
    """Western zodiac sign from a calendar date."""
    m, d = birthday.month, birthday.day
    if (m == 3 and d >= 21) or (m == 4 and d <= 19):
        return "Aries"
    if (m == 4 and d >= 20) or (m == 5 and d <= 20):
        return "Taurus"
    if (m == 5 and d >= 21) or (m == 6 and d <= 20):
        return "Gemini"
    if (m == 6 and d >= 21) or (m == 7 and d <= 22):
        return "Cancer"
    if (m == 7 and d >= 23) or (m == 8 and d <= 22):
        return "Leo"
    if (m == 8 and d >= 23) or (m == 9 and d <= 22):
        return "Virgo"
    if (m == 9 and d >= 23) or (m == 10 and d <= 22):
        return "Libra"
    if (m == 10 and d >= 23) or (m == 11 and d <= 21):
        return "Scorpio"
    if (m == 11 and d >= 22) or (m == 12 and d <= 21):
        return "Sagittarius"
    if (m == 12 and d >= 22) or (m == 1 and d <= 19):
        return "Capricorn"
    if (m == 1 and d >= 20) or (m == 2 and d <= 18):
        return "Aquarius"
    return "Pisces"


def profile_photo_url(user: User) -> Optional[str]:
    if user.profile_photo_key:
        return get_image_url(user.profile_photo_key, internal=False)
    return None


def user_profile_dict(user: User) -> dict[str, Any]:
    zodiac = user.zodiac_sign
    if not zodiac and user.birthday:
        zodiac = compute_zodiac(user.birthday)
    return {
        "user_id": str(user.id),
        "auth_user_id": str(user.auth_user_id) if user.auth_user_id else None,
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "profile_photo_url": profile_photo_url(user),
        "bio": user.bio,
        "birthday": user.birthday.isoformat() if user.birthday else None,
        "zodiac_sign": zodiac,
        "mobile_number": user.mobile_number,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def user_public_dict(user: User) -> dict[str, Any]:
    return {
        "user_id": str(user.id),
        "username": user.username,
        "display_name": user.display_name or user.username,
        "profile_photo_url": profile_photo_url(user),
    }


def generate_username(db: Session, base: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]", "", (base or "user").lower())[:24] or "user"
    candidate = slug
    n = 1
    while db.execute(select(User.id).where(User.username == candidate)).first():
        candidate = f"{slug}{n}"
        n += 1
    return candidate


def parse_birthday(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
