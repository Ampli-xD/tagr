"""Authentication and enrollment routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from auth_util import create_access_token
from db import create_db, embedding_literal
from http_util import UploadedFile, form_field, json_response, parse_multipart
from storage import get_image_url, upload_image
from workers import fetch


async def handle_auth(env, method: str, subpath: str, request, user_id: str | None):
    if method == "POST" and subpath == "register":
        return await register(env, request)
    if method == "POST" and subpath == "verify-otp":
        return await verify_otp(env, request)
    if method == "POST" and subpath == "enroll-face":
        return await enroll_face(env, request)
    if method == "POST" and subpath == "login":
        return await login(env, request)
    if method == "POST" and subpath == "request-login-otp":
        return await request_login_otp(env, request)
    if method == "GET" and subpath == "me":
        if not user_id:
            return json_response({"detail": "Could not validate credentials"}, 401)
        return await me(env, user_id)
    return json_response({"detail": "Not found"}, 404)


async def register(env, request):
    fields, _ = await parse_multipart(request)
    try:
        mobile_number = form_field(fields, "mobile_number")
        username = form_field(fields, "username")
    except ValueError as exc:
        return json_response({"detail": str(exc)}, 400)

    db = create_db(env.DATABASE_URL)
    try:
        existing = db.fetchone(
            "SELECT id FROM users WHERE mobile_number = %s OR username = %s LIMIT 1",
            (mobile_number, username),
        )
        if existing:
            return json_response({"detail": "Username or Mobile number already registered"}, 400)

        user = db.fetchone(
            "INSERT INTO users (mobile_number, username, is_verified) VALUES (%s, %s, false) RETURNING id",
            (mobile_number, username),
        )
        otp_code = "123456"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        db.execute(
            "INSERT INTO otp_requests (mobile_number, otp_code, expires_at) VALUES (%s, %s, %s)",
            (mobile_number, otp_code, expires_at),
        )
        print(f"--- MOCK OTP --- Sent OTP {otp_code} to {mobile_number} (expires in 5 minutes)")
        return json_response({"user_id": str(user["id"]), "otp_sent": True})
    finally:
        db.close()


async def verify_otp(env, request):
    fields, _ = await parse_multipart(request)
    try:
        mobile_number = form_field(fields, "mobile_number")
        otp = form_field(fields, "otp")
    except ValueError as exc:
        return json_response({"detail": str(exc)}, 400)

    db = create_db(env.DATABASE_URL)
    try:
        otp_req = db.fetchone(
            """
            SELECT id, otp_code, verified, expires_at
            FROM otp_requests
            WHERE mobile_number = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (mobile_number,),
        )
        if (
            not otp_req
            or otp_req["otp_code"] != otp
            or otp_req["verified"]
            or otp_req["expires_at"] < datetime.now(timezone.utc)
        ):
            return json_response({"detail": "Invalid, expired or already verified OTP"}, 400)

        db.execute("UPDATE otp_requests SET verified = true WHERE id = %s", (otp_req["id"],))
        user = db.fetchone(
            "UPDATE users SET is_verified = true WHERE mobile_number = %s RETURNING id",
            (mobile_number,),
        )
        if not user:
            return json_response({"detail": "User not found"}, 404)

        token = create_access_token(str(user["id"]), env.JWT_SECRET)
        return json_response({"verified": True, "token": token})
    finally:
        db.close()


async def enroll_face(env, request):
    fields, files = await parse_multipart(request)
    try:
        user_id = form_field(fields, "user_id")
    except ValueError as exc:
        return json_response({"detail": str(exc)}, 400)

    image: UploadedFile | None = files.get("image")
    if not image:
        return json_response({"detail": "image file is required"}, 400)

    db = create_db(env.DATABASE_URL)
    try:
        user = db.fetchone("SELECT id FROM users WHERE id = %s::uuid", (user_id,))
        if not user:
            return json_response({"detail": "User not found"}, 404)

        ext = image.name.split(".")[-1] if "." in image.name else "jpg"
        filename = f"enrollments/{user_id}.{ext}"
        await upload_image(env, image.data, filename, image.content_type)
        storage_url = get_image_url(env, filename, True)

        runsync_url = f"{env.INFERENCE_URL.rstrip('/')}/runsync"
        response = await fetch(
            runsync_url,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=__import__("json").dumps(
                {"input": {"images": [{"image_id": user_id, "url": storage_url}]}}
            ),
        )
        if not response.ok:
            text = await response.text()
            return json_response({"detail": f"Inference service error: {text}"}, 500)

        job_result = await response.json()
        output = job_result.get("output", {})
        if job_result.get("error") or output.get("error"):
            return json_response(
                {"detail": output.get("error") or job_result.get("error") or "Inference job failed"},
                500,
            )

        faces = (output.get("results") or [{}])[0].get("faces") or []
        if not faces:
            return json_response(
                {
                    "detail": "No face detected in the enrollment image. Please try again with a clear photo of your face."
                },
                400,
            )

        embedding = faces[0].get("embedding") or []
        if len(embedding) != 512:
            return json_response({"detail": "Invalid embedding from inference service"}, 500)

        emb_row = db.fetchone(
            """
            INSERT INTO face_embeddings (user_id, embedding, source, source_photo_id)
            VALUES (%s::uuid, %s::vector, 'enrollment', NULL)
            RETURNING id
            """,
            (user_id, embedding_literal(embedding)),
        )
        return json_response({"enrolled": True, "embedding_id": str(emb_row["id"])})
    except Exception as exc:
        return json_response({"detail": f"Could not reach inference service: {exc}"}, 503)
    finally:
        db.close()


async def login(env, request):
    fields, _ = await parse_multipart(request)
    try:
        mobile_number = form_field(fields, "mobile_number")
        otp = form_field(fields, "otp")
    except ValueError as exc:
        return json_response({"detail": str(exc)}, 400)

    db = create_db(env.DATABASE_URL)
    try:
        otp_req = db.fetchone(
            """
            SELECT otp_code, expires_at FROM otp_requests
            WHERE mobile_number = %s ORDER BY created_at DESC LIMIT 1
            """,
            (mobile_number,),
        )
        if (
            not otp_req
            or otp_req["otp_code"] != otp
            or otp_req["expires_at"] < datetime.now(timezone.utc)
        ):
            return json_response({"detail": "Invalid or expired OTP"}, 400)

        user = db.fetchone("SELECT id FROM users WHERE mobile_number = %s", (mobile_number,))
        if not user:
            return json_response({"detail": "User not found. Please register first."}, 404)

        user_id = str(user["id"])
        token = create_access_token(user_id, env.JWT_SECRET)
        return json_response({"token": token, "user_id": user_id})
    finally:
        db.close()


async def request_login_otp(env, request):
    fields, _ = await parse_multipart(request)
    try:
        mobile_number = form_field(fields, "mobile_number")
    except ValueError as exc:
        return json_response({"detail": str(exc)}, 400)

    db = create_db(env.DATABASE_URL)
    try:
        user = db.fetchone(
            "SELECT id, is_verified FROM users WHERE mobile_number = %s",
            (mobile_number,),
        )
        if not user:
            return json_response({"detail": "User not found"}, 404)
        if not user["is_verified"]:
            return json_response({"detail": "User not verified"}, 400)

        otp_code = "123456"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        db.execute(
            "INSERT INTO otp_requests (mobile_number, otp_code, expires_at) VALUES (%s, %s, %s)",
            (mobile_number, otp_code, expires_at),
        )
        print(f"--- MOCK OTP --- Sent OTP {otp_code} to {mobile_number} (expires in 5 minutes)")
        return json_response({"otp_sent": True})
    finally:
        db.close()


async def me(env, user_id: str):
    db = create_db(env.DATABASE_URL)
    try:
        user = db.fetchone(
            "SELECT id, username, mobile_number, created_at FROM users WHERE id = %s::uuid",
            (user_id,),
        )
        if not user:
            return json_response({"detail": "User not found"}, 404)
        return json_response(
            {
                "user_id": str(user["id"]),
                "username": user["username"],
                "mobile_number": user["mobile_number"],
                "created_at": user["created_at"].isoformat()
                if hasattr(user["created_at"], "isoformat")
                else user["created_at"],
            }
        )
    finally:
        db.close()
