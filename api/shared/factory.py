import os
import motor.motor_asyncio
from redis import Redis
from .env import *
from .modules.jackett import AsyncJackett


# Initialize Redis
redis = Redis(
    host=REDIS_HOST,
    password=REDIS_PASSWORD,
    port=REDIS_PORT,
    db=0,
)


jackett = AsyncJackett(apikey=JACKETT_API_KEY, store=redis)

def get_db():
    # Initialize MongoDB
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DATABASE_URI)
    db = mongo_client[MONGO_DATABASE_NAME]
    return db


db = get_db()
