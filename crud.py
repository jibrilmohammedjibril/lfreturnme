import base64
import json
import os

import motor.motor_asyncio
from fastapi import UploadFile

import schemas
import uuid
import bcrypt
import logging
from schemas import Tag, ItemRegistration, Dashboard
from bson import ObjectId
from pymongo import MongoClient
import firebase_admin
from firebase_admin import credentials, storage
from typing import Optional
from pymongo.collection import Collection
from datetime import datetime, timedelta
from pymongo import ReturnDocument

logger = logging.getLogger(__name__)

# MongoDB connection setup
client = motor.motor_asyncio.AsyncIOMotorClient(
    "mongodb+srv://Admin:AITeKaIUZtKdYbvu@lfreturnme.vjjpets.mongodb.net/?retryWrites=true&w=majority&appName=LFReturnMe")
database = client["LFReturnMe"]
db = client["LFReturnMe"]
users_collection = database["users"]
tags_collection = db["tags"]
items_collection = db["items"]
reset_tokens_collection = database["reset_tokens"]
#####

firebase_key_base64 = os.getenv("FIREBASE_KEY_BASE64")
if not firebase_key_base64:
    raise RuntimeError("FIREBASE_KEY_BASE64 environment variable not set")

firebase_key_json = base64.b64decode(firebase_key_base64).decode('utf-8')
firebase_key_dict = json.loads(firebase_key_json)
cred = credentials.Certificate(firebase_key_dict)

# Read Firebase project ID from environment variable
firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")
if not firebase_project_id:
    raise RuntimeError("FIREBASE_PROJECT_ID environment variable not set")

# Initialize Firebase Admin SDK
#initialize_app(cred, {'storageBucket': f'{firebase_project_id}.appspot.com'})
# Initialize Firebase app
#cred = credentials.Certificate("lfreturnme-5a551-firebase-adminsdk-60kvl-8eb9886962.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'lfreturnme-5a551.appspot.com'
})


async def check_credentials(email_address: str) -> bool:
    try:
        count = await users_collection.count_documents({"email_address": email_address})
        logger.debug("check_credentials: email_address=%s, count=%d", email_address, count)
        return count == 0
    except Exception as e:
        logger.error("Error in check_credentials: %s", e)
        raise


async def create_user(user: schemas.Signup) -> schemas.ResponseSignup:
    try:
        user_uuid = str(uuid.uuid4())
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

        if await check_credentials(user.email_address):
            user_data = {
                "uuid": user_uuid,
                "full_name": user.full_name,
                "email_address": user.email_address,
                "date_of_birth": user.date_of_birth.isoformat(),
                "address": user.address,
                "id_no": user.id_no,
                "profile_picture": user.profile_picture,
                "phone_number": user.phone_number,
                "gender": user.gender,
                "valid_id_type": user.valid_id_type,
                "id_card_image": user.id_card_image,
                "password": hashed_password.decode('utf-8'),

            }
            await users_collection.insert_one(user_data)
            logger.info("User created successfully: %s", user_uuid)
            return schemas.ResponseSignup(**user_data)
        else:
            logger.warning("create_user: Email address already exists: %s", user.email_address)
            return None
    except Exception as e:
        logger.error("Error in create_user: %s", e)
        raise


async def authenticate_user(email_address: str, password: str) -> schemas.ResponseSignup:
    try:
        user = await users_collection.find_one({"email_address": email_address})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            logger.info("User authenticated successfully: %s", email_address)
            return schemas.ResponseSignup(**user)
        else:
            logger.warning("Authentication failed for user: %s", email_address)
            return None
    except Exception as e:
        logger.error("Error in authenticate_user: %s", e)
        raise


async def get_tag_by_tag1(tag1: str) -> Optional[Tag]:
    tag_data = await tags_collection.find_one({"tag1": tag1})
    print(tag_data)
    if tag_data:
        return Tag(**tag_data)

    return None


async def update_tag(tag1: str, uuid: str) -> bool:
    result = await tags_collection.update_one(
        {"tag1": tag1},
        {"$set": {"is_owned": True, "uuid": uuid}}
    )
    return result.modified_count > 0


async def save_item_registration(item: ItemRegistration) -> bool:
    item_dict = item.dict()
    result = await items_collection.insert_one(item_dict)
    return result.inserted_id is not None


async def update_user_items(uuid: str, item: ItemRegistration) -> bool:
    user = await users_collection.find_one({"uuid": uuid})
    if user:
        items = user.get("items", {})
        items[item.tag_id] = item.dict()  # Use tag_id as the key and the item dict as the value
        result = await users_collection.update_one(
            {"uuid": uuid},
            {"$set": {"items": items}}
        )
        return result.modified_count > 0
    return False


def upload_to_firebase(file: UploadFile) -> str:
    bucket = storage.bucket()
    blob = bucket.blob(f"{uuid.uuid4()}-{file.filename}")
    blob.upload_from_string(file.file.read(), content_type=file.content_type)
    blob.make_public()
    return blob.public_url


# async def get_user_by_uuid(db: Collection, uuid: str) -> Optional[Dashboard]:
#     user_data = db.find_one({"uuid": uuid})
#     if user_data:
#         user = Dashboard(**user_data)
#         user.registered_items = calculate_registered_items(user)
#         user.lost_items = calculate_lost_items(user)
#         user.found_items = calculate_found_items(user)
#         return user
#     return None


async def create_reset_token(email_address: str) -> str:
    try:
        user = await users_collection.find_one({"email_address": email_address})
        if user:
            token = str(uuid.uuid4())
            expiration_time = datetime.utcnow() + timedelta(hours=1)  # Token valid for 1 hour
            reset_token_data = {
                "email_address": email_address,
                "token": token,
                "expiration_time": expiration_time
            }
            await reset_tokens_collection.insert_one(reset_token_data)
            return token
        else:
            return None
    except Exception as e:
        logger.error("Error in create_reset_token: %s", e)
        raise


async def validate_reset_token(token: str) -> str:
    try:
        token_data = await reset_tokens_collection.find_one(
            {"token": token, "expiration_time": {"$gt": datetime.utcnow()}})
        if token_data:
            return token_data["email_address"]
        else:
            return None
    except Exception as e:
        logger.error("Error in validate_reset_token: %s", e)
        raise


async def update_password(email_address: str, new_password: str) -> bool:
    try:
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        updated_user = await users_collection.find_one_and_update(
            {"email_address": email_address},
            {"$set": {"password": hashed_password.decode('utf-8')}},
            return_document=ReturnDocument.AFTER
        )
        return updated_user is not None
    except Exception as e:
        logger.error("Error in update_password: %s", e)
        raise
