def serialize_preferences(preferences):
    preferences = dict(preferences or {})
    serialized = {}

    if preferences.get("home_view_mode"):
        serialized["home_view_mode"] = preferences.get("home_view_mode")

    if preferences.get("search_view_mode") in {"list", "grid"}:
        serialized["search_view_mode"] = preferences["search_view_mode"]

    serialized["video_quality"] = preferences.get("video_quality", "auto")

    serialized["video_subtitles"] = preferences.get("video_subtitles") or {"enabled":False,"language":"en","auto_match":True}
    serialized["video_audio_language"] = preferences.get("video_audio_language") or "en"

    ftp = dict(preferences.get("ftp") or {})
    if ftp:
        serialized["ftp"] = {
            "enabled": bool(ftp.get("enabled")),
            "username": ftp.get("username") or "",
            "has_password": bool(ftp.get("password_hash")),
            "updated_at": ftp.get("updated_at"),
        }

    updated_at = preferences.get("updated_at")
    if updated_at:
        serialized["updated_at"] = updated_at

    return serialized
