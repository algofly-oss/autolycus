def serialize_preferences(preferences):
    preferences = dict(preferences or {})
    serialized = {}

    if preferences.get("home_view_mode"):
        serialized["home_view_mode"] = preferences.get("home_view_mode")

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
