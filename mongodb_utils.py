import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson.objectid import ObjectId
import logging

logger = logging.getLogger(__name__)

# MongoDB connection setup
client = AsyncIOMotorClient("mongodb+srv://Admin:AITeKaIUZtKdYbvu@lfreturnme.vjjpets.mongodb.net/?retryWrites=true&w=majority&appName=LFReturnMe")
database = client["LFReturnMe"]
fs = AsyncIOMotorGridFSBucket(database)

async def upload_file_to_gridfs(file_data: bytes, filename: str) -> str:
    try:
        file_id = await fs.upload_from_stream(filename, file_data)
        logger.info(f"File uploaded to GridFS with id: {file_id}")
        return str(file_id)
    except Exception as e:
        logger.error(f"Error uploading file to GridFS: {e}")
        raise

async def get_file_from_gridfs(file_id: str) -> bytes:
    try:
        file_data = await fs.open_download_stream(ObjectId(file_id)).read()
        logger.info(f"File retrieved from GridFS with id: {file_id}")
        return file_data
    except Exception as e:
        logger.error(f"Error retrieving file from GridFS: {e}")
        raise
