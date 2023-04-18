import os

# Load API secret key
API_SECRET_KEY = os.environ.get("API_SECRET_KEY", None)
if API_SECRET_KEY is None:
    raise BaseException("Missing API_SECRET_KEY")

# Load env configuration
API_ALGORITHM = os.environ.get("API_ALGORITHM", "HS256")
API_COOKIES_EXPIRE_MINUTES = int(os.environ.get("API_COOKIES_EXPIRE_MINUTES", 43200))

# Load Redis credentials
REDIS_HOST = os.environ.get("REDIS_HOST", None)
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)

# Load mongodb credentials
MONGO_DATABASE_URI = os.environ.get("MONGO_DATABASE_URI", None)
MONGO_DATABASE_NAME = os.environ.get("MONGO_DATABASE_NAME", None)
