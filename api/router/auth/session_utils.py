import datetime
import ipaddress
import re


def is_public_ip(value):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False

    return ip.is_global


def get_client_ip(request):
    header_candidates = []

    for header_name in (
        "cf-connecting-ip",
        "x-real-ip",
        "x-client-ip",
        "x-forwarded-for",
    ):
        header_value = request.headers.get(header_name, "")
        if not header_value:
            continue
        header_candidates.extend(
            ip.strip() for ip in header_value.split(",") if ip.strip()
        )

    for candidate in header_candidates:
        if is_public_ip(candidate):
            return candidate

    if header_candidates:
        return header_candidates[0]

    return getattr(request.client, "host", "") if request.client else ""


def parse_user_agent(user_agent):
    user_agent = user_agent or ""

    if "Edg/" in user_agent:
        browser = "Edge"
    elif "Chrome/" in user_agent and "Chromium/" not in user_agent:
        browser = "Chrome"
    elif "Firefox/" in user_agent:
        browser = "Firefox"
    elif "Safari/" in user_agent and "Chrome/" not in user_agent:
        browser = "Safari"
    else:
        browser = "Unknown browser"

    if "Windows" in user_agent:
        os_name = "Windows"
    elif "Mac OS X" in user_agent or "Macintosh" in user_agent:
        os_name = "macOS"
    elif "Android" in user_agent:
        os_name = "Android"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        os_name = "iOS"
    elif "Linux" in user_agent:
        os_name = "Linux"
    else:
        os_name = "Unknown OS"

    if re.search(r"Mobile|iPhone|Android", user_agent):
        device_type = "Mobile"
    elif "iPad" in user_agent or "Tablet" in user_agent:
        device_type = "Tablet"
    else:
        device_type = "Desktop"

    return {
        "browser": browser,
        "os": os_name,
        "device_type": device_type,
        "device_name": f"{browser} on {os_name}",
    }


def build_session_metadata(request):
    user_agent = request.headers.get("user-agent", "")
    request_ip = get_client_ip(request)

    return {
        **parse_user_agent(user_agent),
        "ip": request_ip,
        "user_agent": user_agent,
    }


async def create_session_record(db, user_id, session_token, request):
    if not session_token:
        return

    now = datetime.datetime.utcnow()
    await db.user_sessions.update_one(
        {"_id": session_token},
        {
            "$set": {
                "user_id": str(user_id),
                "token": session_token,
                **build_session_metadata(request),
                "last_accessed_at": now,
                "revoked_at": None,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )


async def touch_session_record(db, session_token, request):
    if not session_token:
        return 0

    metadata = build_session_metadata(request)
    metadata.pop("ip", None)
    result = await db.user_sessions.update_one(
        {"_id": session_token, "revoked_at": None},
        {
            "$set": {
                **metadata,
                "last_accessed_at": datetime.datetime.utcnow(),
            }
        },
    )
    return result.matched_count


async def revoke_session_record(db, redis, session_token):
    if not session_token:
        return

    redis.delete(session_token)
    await db.user_sessions.update_one(
        {"_id": session_token},
        {"$set": {"revoked_at": datetime.datetime.utcnow()}},
    )


def serialize_session(session, current_session_token=None):
    def serialize_datetime(value):
        if not value:
            return None
        if value.tzinfo is None:
            return f"{value.isoformat()}Z"
        return value.isoformat()

    return {
        "id": session.get("_id"),
        "device_name": session.get("device_name") or "Unknown device",
        "device_type": session.get("device_type") or "Unknown",
        "browser": session.get("browser") or "Unknown browser",
        "os": session.get("os") or "Unknown OS",
        "ip": session.get("ip") or "Unknown IP",
        "created_at": serialize_datetime(session.get("created_at")),
        "last_accessed_at": serialize_datetime(session.get("last_accessed_at")),
        "current": session.get("_id") == current_session_token,
    }
