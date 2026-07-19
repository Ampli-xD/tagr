"""Social, gallery, notifications, and friends routes."""

from __future__ import annotations

from db import create_db
from http_util import json_response, parse_json, parse_query
from storage import get_image_url


async def handle_social(env, method: str, path: str, request, user_id: str | None):
  if path == "notifications" and method == "GET":
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    return await get_notifications(env, request, user_id)

  if path.startswith("notifications/") and path.endswith("/read") and method == "PATCH":
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    notification_id = path.split("/")[1]
    return await read_notification(env, notification_id, user_id)

  if path.startswith("users/") and path.endswith("/gallery") and method == "GET":
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    target_user_id = path.split("/")[1]
    return await get_user_gallery(env, request, target_user_id)

  if path.startswith("users/") and path.endswith("/embeddings") and method == "GET":
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    target_user_id = path.split("/")[1]
    return await get_user_embeddings(env, target_user_id)

  if path.startswith("photos/") and path.endswith("/comments") and method == "GET":
    photo_id = path.split("/")[1]
    return await list_comments(env, photo_id)

  if path.startswith("photos/") and path.endswith("/comments") and method == "POST":
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    photo_id = path.split("/")[1]
    return await add_comment(env, photo_id, request, user_id)

  if path.startswith("photos/") and method == "GET" and path.count("/") == 1:
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    photo_id = path.split("/")[1]
    return await get_photo_details(env, photo_id)

  if path == "friends/suggestions" and method == "GET":
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    return await get_friend_suggestions(env, user_id)

  if path == "friends/request" and method == "POST":
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    return await send_friend_request(env, request, user_id)

  if path.startswith("friends/request/") and path.endswith("/respond") and method == "POST":
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    request_id = path.split("/")[2]
    return await respond_friend_request(env, request_id, request, user_id)

  if path == "friends" and method == "GET":
    if not user_id:
      return json_response({"detail": "Could not validate credentials"}, 401)
    return await list_friends(env, user_id)

  return json_response({"detail": "Not found"}, 404)


async def get_notifications(env, request, current_user_id: str):
  query = parse_query(request.url)
  unread_only = query.get("unread_only") == "true"
  db = create_db(env.DATABASE_URL)
  try:
    if unread_only:
      rows = db.fetchall(
        """
        SELECT n.id, n.type, n.photo_id, n.actor_user_id, n.is_read, n.created_at,
               u.username AS actor_username
        FROM notifications n
        LEFT JOIN users u ON n.actor_user_id = u.id
        WHERE n.user_id = %s::uuid AND n.is_read = false
        ORDER BY n.created_at DESC
        """,
        (current_user_id,),
      )
    else:
      rows = db.fetchall(
        """
        SELECT n.id, n.type, n.photo_id, n.actor_user_id, n.is_read, n.created_at,
               u.username AS actor_username
        FROM notifications n
        LEFT JOIN users u ON n.actor_user_id = u.id
        WHERE n.user_id = %s::uuid
        ORDER BY n.created_at DESC
        """,
        (current_user_id,),
      )
    return json_response(
      {
        "notifications": [
          {
            "notification_id": str(row["id"]),
            "type": row["type"],
            "photo_id": str(row["photo_id"]) if row["photo_id"] else None,
            "actor_user_id": str(row["actor_user_id"]) if row["actor_user_id"] else None,
            "actor_username": row["actor_username"],
            "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
            "read": row["is_read"],
          }
          for row in rows
        ]
      }
    )
  finally:
    db.close()


async def read_notification(env, notification_id: str, current_user_id: str):
  db = create_db(env.DATABASE_URL)
  try:
    row = db.fetchone(
      """
      UPDATE notifications SET is_read = true
      WHERE id = %s::uuid AND user_id = %s::uuid
      RETURNING id
      """,
      (notification_id, current_user_id),
    )
    if not row:
      return json_response({"detail": "Notification not found"}, 404)
    return json_response({"updated": True})
  finally:
    db.close()


async def get_user_gallery(env, request, user_id: str):
  query = parse_query(request.url)
  page = max(1, int(query.get("page", "1")))
  limit = max(1, int(query.get("limit", "20")))
  offset = (page - 1) * limit
  db = create_db(env.DATABASE_URL)
  try:
    photos = db.fetchall(
      """
      SELECT DISTINCT p.id, p.owner_id, p.storage_url, p.uploaded_at
      FROM photos p
      JOIN photo_tags pt ON p.id = pt.photo_id
      WHERE pt.user_id = %s::uuid
      ORDER BY p.uploaded_at DESC
      OFFSET %s LIMIT %s
      """,
      (user_id, offset, limit),
    )
    photos_list = []
    for photo in photos:
      tags = db.fetchall(
        """
        SELECT pt.user_id, u.username
        FROM photo_tags pt
        JOIN users u ON pt.user_id = u.id
        WHERE pt.photo_id = %s::uuid
        """,
        (str(photo["id"]),),
      )
      photos_list.append(
        {
          "photo_id": str(photo["id"]),
          "url": get_image_url(env, photo["storage_url"], False),
          "uploaded_by": str(photo["owner_id"]),
          "uploaded_at": photo["uploaded_at"].isoformat() if hasattr(photo["uploaded_at"], "isoformat") else photo["uploaded_at"],
          "tagged_users": [
            {"user_id": str(tag["user_id"]), "username": tag["username"]} for tag in tags
          ],
        }
      )
    return json_response({"photos": photos_list})
  finally:
    db.close()


async def get_photo_details(env, photo_id: str):
  db = create_db(env.DATABASE_URL)
  try:
    photo = db.fetchone(
      "SELECT id, owner_id, storage_url, status FROM photos WHERE id = %s::uuid",
      (photo_id,),
    )
    if not photo:
      return json_response({"detail": "Photo not found"}, 404)

    tags = db.fetchall(
      """
      SELECT pt.id, pt.user_id, u.username, pt.bbox_x, pt.bbox_y,
             pt.bbox_width, pt.bbox_height, pt.confidence, pt.source
      FROM photo_tags pt
      JOIN users u ON pt.user_id = u.id
      WHERE pt.photo_id = %s::uuid
      """,
      (photo_id,),
    )
    comments = db.fetchall(
      """
      SELECT c.id, c.user_id, u.username, c.text, c.created_at
      FROM comments c
      JOIN users u ON c.user_id = u.id
      WHERE c.photo_id = %s::uuid
      ORDER BY c.created_at ASC
      """,
      (photo_id,),
    )
    return json_response(
      {
        "photo_id": str(photo["id"]),
        "url": get_image_url(env, photo["storage_url"], False),
        "owner_id": str(photo["owner_id"]),
        "status": photo["status"],
        "tags": [
          {
            "tag_id": str(tag["id"]),
            "user_id": str(tag["user_id"]),
            "username": tag["username"],
            "bbox": {
              "x": tag["bbox_x"],
              "y": tag["bbox_y"],
              "width": tag["bbox_width"],
              "height": tag["bbox_height"],
            },
            "confidence": tag["confidence"],
            "source": tag["source"],
          }
          for tag in tags
        ],
        "comments": [
          {
            "comment_id": str(comment["id"]),
            "user_id": str(comment["user_id"]),
            "username": comment["username"],
            "text": comment["text"],
            "created_at": comment["created_at"].isoformat() if hasattr(comment["created_at"], "isoformat") else comment["created_at"],
          }
          for comment in comments
        ],
      }
    )
  finally:
    db.close()


async def add_comment(env, photo_id: str, request, current_user_id: str):
  payload = await parse_json(request)
  text_content = payload.get("text")
  if not text_content:
    return json_response({"detail": "Comment text is required"}, 400)

  db = create_db(env.DATABASE_URL)
  try:
    photo = db.fetchone("SELECT id FROM photos WHERE id = %s::uuid", (photo_id,))
    if not photo:
      return json_response({"detail": "Photo not found"}, 404)

    comment = db.fetchone(
      """
      INSERT INTO comments (photo_id, user_id, text)
      VALUES (%s::uuid, %s::uuid, %s)
      RETURNING id
      """,
      (photo_id, current_user_id, text_content),
    )
    return json_response({"comment_id": str(comment["id"]), "created": True})
  finally:
    db.close()


async def list_comments(env, photo_id: str):
  db = create_db(env.DATABASE_URL)
  try:
    comments = db.fetchall(
      """
      SELECT c.id, c.user_id, u.username, c.text, c.created_at
      FROM comments c
      JOIN users u ON c.user_id = u.id
      WHERE c.photo_id = %s::uuid
      ORDER BY c.created_at ASC
      """,
      (photo_id,),
    )
    return json_response(
      {
        "comments": [
          {
            "comment_id": str(comment["id"]),
            "user_id": str(comment["user_id"]),
            "username": comment["username"],
            "text": comment["text"],
            "created_at": comment["created_at"].isoformat() if hasattr(comment["created_at"], "isoformat") else comment["created_at"],
          }
          for comment in comments
        ]
      }
    )
  finally:
    db.close()


async def get_friend_suggestions(env, current_user_id: str):
  db = create_db(env.DATABASE_URL)
  try:
    rows = db.fetchall(
      """
      SELECT pt2.user_id AS suggested_id, u.username, COUNT(pt1.photo_id)::int AS mutual_photos
      FROM photo_tags pt1
      JOIN photo_tags pt2 ON pt1.photo_id = pt2.photo_id AND pt1.user_id != pt2.user_id
      JOIN users u ON pt2.user_id = u.id
      WHERE pt1.user_id = %s::uuid
        AND NOT EXISTS (
          SELECT 1 FROM friendships f
          WHERE (f.user_a_id = %s::uuid AND f.user_b_id = pt2.user_id)
             OR (f.user_b_id = %s::uuid AND f.user_a_id = pt2.user_id)
        )
        AND NOT EXISTS (
          SELECT 1 FROM friend_requests fr
          WHERE (fr.from_user_id = %s::uuid AND fr.to_user_id = pt2.user_id)
             OR (fr.from_user_id = pt2.user_id AND fr.to_user_id = %s::uuid)
        )
      GROUP BY pt2.user_id, u.username
      ORDER BY mutual_photos DESC
      """,
      (current_user_id, current_user_id, current_user_id, current_user_id, current_user_id),
    )
    return json_response(
      {
        "suggestions": [
          {
            "user_id": str(row["suggested_id"]),
            "username": row["username"],
            "mutual_photo_count": row["mutual_photos"],
          }
          for row in rows
        ]
      }
    )
  finally:
    db.close()


async def send_friend_request(env, request, current_user_id: str):
  payload = await parse_json(request)
  target_user_id = payload.get("target_user_id")
  if not target_user_id:
    return json_response({"detail": "target_user_id is required"}, 400)
  if current_user_id == target_user_id:
    return json_response({"detail": "Cannot send friend request to yourself"}, 400)

  db = create_db(env.DATABASE_URL)
  try:
    target = db.fetchone("SELECT id FROM users WHERE id = %s::uuid", (target_user_id,))
    if not target:
      return json_response({"detail": "Target user not found"}, 404)

    friendship = db.fetchone(
      """
      SELECT id FROM friendships
      WHERE (user_a_id = %s::uuid AND user_b_id = %s::uuid)
         OR (user_a_id = %s::uuid AND user_b_id = %s::uuid)
      """,
      (current_user_id, target_user_id, target_user_id, current_user_id),
    )
    if friendship:
      return json_response({"detail": "Already friends with this user"}, 400)

    existing = db.fetchone(
      """
      SELECT id, status FROM friend_requests
      WHERE (from_user_id = %s::uuid AND to_user_id = %s::uuid)
         OR (from_user_id = %s::uuid AND to_user_id = %s::uuid)
      LIMIT 1
      """,
      (current_user_id, target_user_id, target_user_id, current_user_id),
    )
    if existing:
      return json_response({"request_id": str(existing["id"]), "status": existing["status"]})

    req = db.fetchone(
      """
      INSERT INTO friend_requests (from_user_id, to_user_id, origin, status)
      VALUES (%s::uuid, %s::uuid, 'explicit', 'pending')
      RETURNING id
      """,
      (current_user_id, target_user_id),
    )
    return json_response({"request_id": str(req["id"]), "status": "pending"})
  finally:
    db.close()


async def respond_friend_request(env, request_id: str, request, current_user_id: str):
  payload = await parse_json(request)
  action = payload.get("action")
  if action not in ("accept", "reject"):
    return json_response({"detail": "Action must be 'accept' or 'reject'"}, 400)

  db = create_db(env.DATABASE_URL)
  try:
    req = db.fetchone(
      "SELECT id, from_user_id, to_user_id, status FROM friend_requests WHERE id = %s::uuid",
      (request_id,),
    )
    if not req or str(req["to_user_id"]) != current_user_id:
      return json_response({"detail": "Request not found or not addressed to you"}, 404)
    if req["status"] != "pending":
      return json_response({"detail": "Request already processed"}, 400)

    if action == "reject":
      db.execute(
        "UPDATE friend_requests SET status = 'rejected', responded_at = NOW() WHERE id = %s::uuid",
        (request_id,),
      )
      return json_response({"updated": True})

    db.execute(
      "UPDATE friend_requests SET status = 'accepted', responded_at = NOW() WHERE id = %s::uuid",
      (request_id,),
    )
    sorted_ids = sorted([str(req["from_user_id"]), str(req["to_user_id"])])
    user_a, user_b = sorted_ids
    exists = db.fetchone(
      "SELECT id FROM friendships WHERE user_a_id = %s::uuid AND user_b_id = %s::uuid",
      (user_a, user_b),
    )
    if not exists:
      db.execute(
        "INSERT INTO friendships (user_a_id, user_b_id) VALUES (%s::uuid, %s::uuid)",
        (user_a, user_b),
      )
    return json_response({"updated": True})
  finally:
    db.close()


async def list_friends(env, current_user_id: str):
  db = create_db(env.DATABASE_URL)
  try:
    rows = db.fetchall(
      """
      SELECT u.id, u.username, f.created_at
      FROM friendships f
      JOIN users u ON (
        (u.id = f.user_a_id AND f.user_b_id = %s::uuid)
        OR (u.id = f.user_b_id AND f.user_a_id = %s::uuid)
      )
      """,
      (current_user_id, current_user_id),
    )
    return json_response(
      {
        "friends": [
          {
            "user_id": str(row["id"]),
            "username": row["username"],
            "since": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
          }
          for row in rows
        ]
      }
    )
  finally:
    db.close()


async def get_user_embeddings(env, user_id: str):
  db = create_db(env.DATABASE_URL)
  try:
    rows = db.fetchall(
      """
      SELECT id, source, created_at
      FROM face_embeddings
      WHERE user_id = %s::uuid
      ORDER BY created_at DESC
      """,
      (user_id,),
    )
    return json_response(
      {
        "user_id": user_id,
        "embeddings": [
          {
            "embedding_id": str(row["id"]),
            "source": row["source"],
            "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
          }
          for row in rows
        ],
      }
    )
  finally:
    db.close()
