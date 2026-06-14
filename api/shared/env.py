import os

# Load API secret key
API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "8d1f3e4d46d04f5fac089a8f980f1951")
if API_SECRET_KEY is None:
    raise BaseException("Missing API_SECRET_KEY")

# Load env configuration
API_ALGORITHM = os.environ.get("API_ALGORITHM", "HS256")
API_COOKIES_EXPIRE_MINUTES = int(os.environ.get("API_COOKIES_EXPIRE_MINUTES", 43200))
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "session_token")

# Load Redis credentials
REDIS_HOST = os.environ.get("REDIS_HOST", None)
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)

# Load mongodb credentials
MONGO_DATABASE_URI = os.environ.get("MONGO_DATABASE_URI", None)
MONGO_DATABASE_NAME = os.environ.get("MONGO_DATABASE_NAME", None)

JACKETT_API_KEY = os.environ.get("JACKETT_API_KEY", None)

# Load Meilisearch configuration
MEILI_SEARCH_HOST = os.environ.get("MEILI_SEARCH_HOST", "http://meilisearch:7700")
MEILI_SEARCH_API_KEY = os.environ.get("MEILI_SEARCH_API_KEY", None)
MEILI_SEARCH_INDEX_NAME_PREFIX = os.environ.get(
    "MEILI_SEARCH_INDEX_NAME_PREFIX", "autolycus"
)
MEILI_SEARCH_MAX_TOTAL_HITS = int(os.environ.get("MEILI_SEARCH_MAX_TOTAL_HITS", 20000))

# Optional movie metadata provider. If unset, downloads keep working and the UI
# falls back to parsed local metadata.
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", None)
TMDB_READ_ACCESS_TOKEN = os.environ.get("TMDB_READ_ACCESS_TOKEN", None)
TMDB_LANGUAGE = os.environ.get("TMDB_LANGUAGE", "en-US")

# FTP service configuration. FTP is served by SFTPGo; the API only manages
# credentials/settings and handles SFTPGo's internal auth hook.
FTP_PUBLIC_HOST = os.environ.get("FTP_PUBLIC_HOST", "")
FTP_PUBLIC_PORT = os.environ.get("FTP_PUBLIC_PORT", os.environ.get("FTP_HOST_PORT", "2121"))
FTP_HOOK_SECRET = os.environ.get("FTP_HOOK_SECRET", "")
