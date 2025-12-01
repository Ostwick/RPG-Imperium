from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

# Create Client
client = AsyncIOMotorClient(settings.MONGO_URL)

# Get Database
db = client[settings.DB_NAME]

# Helper to get collections
users_collection = db["users"]
characters_collection = db["characters"]