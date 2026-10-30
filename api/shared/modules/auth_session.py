"""Persistent first-party cookies and durable, revocable session recovery."""
import datetime
import os

from bson import ObjectId
from bson.errors import InvalidId
from shared.env import API_COOKIES_EXPIRE_MINUTES, SESSION_COOKIE_NAME

SESSION_SECONDS = max(60, API_COOKIES_EXPIRE_MINUTES * 60)
RENEW_SECONDS = min(3600, SESSION_SECONDS // 2)


def set_session_cookie(response, request, token):
    configured = os.environ.get("SESSION_COOKIE_SECURE", "auto").lower()
    secure = request.url.scheme == "https" if configured == "auto" else configured in ("1", "true", "yes")
    response.set_cookie(SESSION_COOKIE_NAME, token, max_age=SESSION_SECONDS,
                        expires=SESSION_SECONDS, httponly=True, secure=secure,
                        samesite="lax", path="/")


async def resolve_session(token, renew=True):
    # Import lazily: the factory also loads modules used by Celery workers.
    from shared.factory import db, redis
    if not token:
        return None, False
    pipe = redis.pipeline(transaction=False)
    pipe.get(token)
    pipe.ttl(token)
    checkpoint_key = "auth_session_renew/" + token
    pipe.get(checkpoint_key)
    user_id, ttl, checkpoint = pipe.execute()
    if user_id and ttl > 0 and not renew:
        return user_id, False
    if user_id and ttl > SESSION_SECONDS - RENEW_SECONDS and checkpoint:
        # Renew the browser and cache on each access, checkpoint Mongo hourly.
        redis.expire(token, SESSION_SECONDS)
        return user_id, True

    record = await db.user_sessions.find_one({"_id": token})
    now = datetime.datetime.utcnow()
    if record and (record.get("revoked_at") is not None or
                   (record.get("expires_at") and record["expires_at"] <= now)):
        redis.delete(token)
        return None, False
    if not user_id:
        # Only a durable active session can restore an evicted Redis entry.
        if not record or not record.get("user_id"):
            return None, False
        try:
            user = await db.users.find_one({"_id": ObjectId(record["user_id"])}, {"_id": 1})
        except (InvalidId, TypeError, ValueError):
            return None, False
        if not user:
            return None, False
        user_id = str(record["user_id"]).encode()

    if renew:
        # Cover accesses since the latest hourly checkpoint during cache loss.
        expires = now + datetime.timedelta(seconds=SESSION_SECONDS + RENEW_SECONDS)
        await db.user_sessions.update_one(
            {"_id": token, "revoked_at": None},
            {"$set": {"user_id": user_id.decode(), "last_accessed_at": now, "expires_at": expires},
             "$setOnInsert": {"created_at": now, "revoked_at": None}}, upsert=True)
        redis.set(token, user_id, ex=SESSION_SECONDS)
        redis.set(checkpoint_key, "1", ex=RENEW_SECONDS)
        return user_id, True

    # A WebSocket handshake cannot renew a browser cookie. Restore only the
    # remaining server lifetime; the next HTTP request can renew both together.
    remaining = SESSION_SECONDS
    if record and record.get("expires_at"):
        remaining = max(1, int((record["expires_at"] - now).total_seconds()))
    redis.set(token, user_id, ex=remaining)
    return user_id, False
