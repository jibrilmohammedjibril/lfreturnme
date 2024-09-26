import base64
import json
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import random
import httpx
import motor.motor_asyncio
from fastapi import UploadFile, HTTPException, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorClient
import schemas
import uuid
import bcrypt
import logging
from schemas import Tag, ItemRegistration, Dashboard, UpdateProfileRequest
from bson import ObjectId
from pymongo import MongoClient
import firebase_admin
from firebase_admin import credentials, storage
from typing import Optional
from pymongo.collection import Collection
from datetime import datetime, timedelta
from pymongo import ReturnDocument
from dotenv import load_dotenv
import hmac
import hashlib
import anyio

load_dotenv()

logger = logging.getLogger(__name__)

# MongoDB connection setup
client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGODB_URL"))
db = client[os.getenv("DATABASE_NAME")]
users_collection = db["users"]
tags_collection = db["tags"]
items_collection = db["items"]
reset_tokens_collection = db["reset_tokens"]
newsletters_collection = db["newsletters"]
otp_collection = db["otp_collection"]

firebase_key_base64 = os.getenv("FIREBASE_KEY_BASE64")
if not firebase_key_base64:
    raise RuntimeError("FIREBASE_KEY_BASE64 environment variable not set")

firebase_key_json = base64.b64decode(firebase_key_base64).decode('utf-8')
firebase_key_dict = json.loads(firebase_key_json)
cred = credentials.Certificate(firebase_key_dict)
firebase_admin.initialize_app(cred, {
    'storageBucket': os.getenv("FIREBASE_PROJECT_ID_INIT")})

paystack_secret_key = os.getenv("PAYSTACK_SECRET_KEY")
paystack_base_url = os.getenv("PAYSTACK_BASE_URL")


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
                "is_verified": user.is_verified

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
        if not user:
            logger.warning("User does not exist: %s", email_address)
            raise HTTPException(status_code=404, detail="User does not exist")
        if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            logger.info("User authenticated successfully: %s", email_address)
            return schemas.ResponseSignup(**user)
        else:
            logger.warning("Invalid password for user: %s", email_address)
            raise HTTPException(status_code=400, detail="Invalid password")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("Error in authenticate_user: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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


from urllib.parse import unquote


def delete_from_firebase(url: str) -> None:
    bucket = storage.bucket()
    # Extract the blob name from the URL
    blob_name = url.split("lfreturnme-5a551.appspot.com/")[-1]
    # Decode percent-encoded characters
    blob_name = unquote(blob_name)
    blob = bucket.blob(blob_name)
    blob.delete()


async def create_reset_token(email_address: str) -> str:
    try:
        user = await users_collection.find_one({"email_address": email_address})
        if user:
            token = str(uuid.uuid4())
            expiration_time = datetime.utcnow() + timedelta(minutes=5)  # Token valid for 5 minutes
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


async def add_newsletter_email(email: str) -> bool:
    try:
        existing_email = await newsletters_collection.find_one({"email": email})
        if existing_email:
            return False
        await newsletters_collection.insert_one({"email": email})
        return True
    except Exception as e:
        logger.error("Error in add_newsletter_email: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


async def add_to_lost(lostfound: schemas.LostFound):
    result = await db.lost.insert_one(lostfound.dict())
    return str(result.inserted_id)


async def add_to_found(lostfound: schemas.LostFound):
    result = await db.found.insert_one(lostfound.dict())
    return str(result.inserted_id)


async def find_item_by_tag_id(tag_id: str) -> Optional[ItemRegistration]:
    print(tag_id)
    item = await items_collection.find_one({"tag_id": tag_id})
    return ItemRegistration(**item)


async def update_item_status(tag_id: str):
    result = await db.items.update_one({"tag_id": tag_id}, {"$set": {"status": "1"}})
    return result.modified_count > 0


async def find_user_by_uuid(uuid: str):
    user = await db.users.find_one({"uuid": uuid})
    return user


async def update_item_status_full(uuid: str, tagid: str, new_status: str, users_collection, items_collection):
    try:
        # Find user by UUID
        user = await users_collection.find_one({"uuid": uuid})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if the item with the given tagid exists in the user's items
        if tagid not in user.get("items", {}):
            raise HTTPException(status_code=404, detail=f"Item with tag ID {tagid} not found for user")

        # Update the item's status in the user's items
        user["items"][tagid]["status"] = str(new_status)

        # Update user document with the modified items dictionary
        user_result = await users_collection.update_one(
            {"uuid": uuid},
            {"$set": {"items": user["items"]}}
        )

        if user_result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update item status in user's items")

        # Find item in the items collection by tagid
        item = await items_collection.find_one({"tag_id": tagid})
        if not item:
            raise HTTPException(status_code=404, detail="Item not found in items collection")

        # Update the item's status in the items collection
        item_result = await items_collection.update_one(
            {"tag_id": tagid},
            {"$set": {"status": new_status}}
        )

        if item_result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update item status in items collection")

        return {"message": "Item status updated successfully", "item_tagid": tagid, "new_status": new_status}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_user_by_uuid(user_uuid: str):
    return await users_collection.find_one({"uuid": user_uuid})


async def update_user_profile(user_uuid: str, update_data: dict):
    result = await users_collection.update_one(
        {"uuid": user_uuid},
        {"$set": update_data}
    )
    return result


def generate_otp():
    return random.randint(100000, 999999)


# Function to send email with OTP
def send_email_otp(receiver_email: str, otp: int):
    try:
        sender_email = os.getenv("EMAIL_USER")
        sender_password = os.getenv("EMAIL_PASS")
        sender_host = os.getenv("EMAIL_HOST")
        # Create the email content
        message = MIMEMultipart("alternative")
        message["Subject"] = "Your OTP Code"
        message["From"] = sender_email
        message["To"] = receiver_email

        text = f"Your OTP code is {otp}. It is valid for 5 minutes."
        html = f"""\
        <html>
          <body>
            <p>Your OTP code is <strong>{otp}</strong>.<br>
               It is valid for 5 minutes.<br>
               Please use it to complete your verification process.
            </p>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)

        server = smtplib.SMTP_SSL(sender_host, 465)  # Using Gmail's SMTP server
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, message.as_string())
        server.quit()

        print(f"OTP sent successfully to {receiver_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send OTP email")


def send_email(to_email: str, subject: str, body: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = 'lostfound_no_reply@lfreturnme.com'
    msg["To"] = to_email
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")
    sender_host = os.getenv("EMAIL_HOST")

    with smtplib.SMTP_SSL(sender_host, 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        print("Email sent successfully!")


async def verify_user_email(email: str):
    # Find the user by email
    user = await users_collection.find_one({"email_address": email})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update the is_verified field to True
    result = await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True}}
    )

    if result.modified_count == 1:
        return {"message": "User verification status updated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to update user verification status")


async def update_user_subscription(subscription_code: str, subscription_status: str, tier: Optional[str] = None):
    # Find the user by the subscription code (assuming you store this in the user's document)
    user = users_collection.find_one({"items.tag_id": subscription_code})

    if user:
        # Update the user's tag information
        update_fields = {
            f"items.{subscription_code}.subscription_status": subscription_status,
        }

        if tier:
            update_fields[f"items.{subscription_code}.tier"] = tier

        await users_collection.update_one(
            {"_id": ObjectId(user["_id"]), f"items.{subscription_code}.tag_id": subscription_code},
            {"$set": update_fields}
        )
        return {"message": f"Subscription status for {subscription_code} updated successfully."}

    return {"message": f"Subscription code {subscription_code} not found."}


async def get_active_subscriptions():
    headers = {
        "Authorization": f"Bearer {paystack_secret_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{paystack_base_url}/subscription", headers=headers)
        data = response.json()
        active_subscriptions = [sub for sub in data['data'] if sub['status'] == 'active']
        return active_subscriptions


def send_email_webhook(cleaned_email: str):
    try:
        # Example sending email logic using smtplib
        sender_email = os.getenv("EMAIL_USER")  # Replace with your sender email
        receiver_email = cleaned_email
        subject = "Subscription Update"
        body = f"Hello, your subscription has been updated successfully."

        # Setup the email
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = receiver_email

        # Send the email
        with smtplib.SMTP_SSL(os.getenv("EMAIL_HOST"), 465) as server:  # Replace with your SMTP server and port
            server.login(sender_email, os.getenv("EMAIL_PASS"))  # Replace with your email password
            server.sendmail(sender_email, receiver_email, msg.as_string())
            server.quit()
        logging.info(f"Email sent to {cleaned_email}")
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")


def clean_email(email: str) -> str:
    # Split email into prefix and domain
    prefix, domain = email.split('@')

    # Remove numbers from the prefix
    cleaned_prefix = re.sub(r'\d+', '', prefix)

    # Return the cleaned email with domain
    return f"{cleaned_prefix}@{domain}"


def verify_paystack_signature(payload: str, paystack_signature: str) -> bool:
    # Your Paystack secret key
    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

    if not PAYSTACK_SECRET_KEY:
        logging.error("PAYSTACK_SECRET_KEY is not set.")
        return False

    # Generate a hash with the secret key and payload
    generated_signature = hmac.new(
        PAYSTACK_SECRET_KEY.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha512
    ).hexdigest()

    # Compare the generated signature with the one from the webhook
    return hmac.compare_digest(generated_signature, paystack_signature)


# def process_paystack_event(data: dict, background_tasks: BackgroundTasks):
#     try:
#         # Extract metadata and custom_fields
#         metadata = data.get('metadata', {})
#         custom_fields = metadata.get('custom_fields', [])
#
#         # Log the entire custom_fields for debugging
#         logging.debug(f"Full custom_fields: {custom_fields}")
#
#         # Extract the tag_id from custom_fields
#         tag_id = next((field.get('value') for field in custom_fields if field.get('variable_name') == 'tag_id'), None)
#
#         if not tag_id:
#             logging.warning(f"tag_id not found in custom_fields: {custom_fields}")
#             return
#
#         logging.info(f"tag_id found: {tag_id}")
#
#         # Extract email from customer data
#         customer = data.get('customer', {})
#         email = customer.get('email')
#
#         # Ensure async database calls are handled correctly
#         async def async_process():
#             item = await items_collection.find_one({'tag_id': tag_id})
#
#             if item:
#                 update_fields = {}
#
#                 # Determine subscription status and tier
#                 if 'plan' in data and data['plan']:
#                     update_fields['subscription_status'] = 'active'
#                     update_fields['tier'] = data['plan'].get('name', item.get('tier', ''))
#                 else:
#                     update_fields['subscription_status'] = 'one-time'
#                     amount = data.get('amount', 0) / 100
#                     update_fields['tier'] = 'Basic' if amount == 250 else 'Premium' if amount == 500 else 'Standard'
#
#                 await items_collection.update_one({'_id': item['_id']}, {'$set': update_fields})
#
#                 if email:
#                     await items_collection.update_one({'_id': item['_id']}, {'$set': {'email_address': email}})
#                     uuid = item.get('uuid')
#                     logging.info(f"uuid found: {uuid}")
#                     if uuid:
#                         user = await users_collection.find_one({'uuid': uuid})
#                         if user:
#                             user_items = user.get('items', {})
#                             if tag_id in user_items:
#                                 user_item = user_items[tag_id]
#                                 user_item['email_address'] = email
#                                 await users_collection.update_one({'_id': user['_id']}, {'$set': {f'items.{tag_id}': user_item}})
#
#                                 logging.info(f"Updated email for tag {tag_id}: {email}")
#                             else:
#                                 logging.warning(f"Tag {tag_id} not found in user's items.")
#                         else:
#                             logging.warning(f"User with uuid {uuid} not found.")
#
#                         cleaned_email = clean_email(email)
#                         background_tasks.add_task(send_email_webhook, cleaned_email)
#
#         # Run async function in the background task
#         anyio.from_thread.run(async_process)
#
#     except Exception as e:
#         logging.error(f"Error processing Paystack event: {str(e)}")
#
#
# # Dummy implementations for the sake of example, you should replace these with actual functionality
#


def process_paystack_event(data: dict, background_tasks: BackgroundTasks):
    try:
        # Extract metadata and custom_fields
        metadata = data.get('metadata', {})
        custom_fields = metadata.get('custom_fields', [])

        # Log the entire custom_fields for debugging
        logging.debug(f"Full custom_fields: {custom_fields}")

        # Extract the tag_id from custom_fields
        tag_id = next((field.get('value') for field in custom_fields if field.get('variable_name') == 'tag_id'), None)

        if not tag_id:
            logging.warning(f"tag_id not found in custom_fields: {custom_fields}")
            return

        # Ensure tag_id is a string
        tag_id = str(tag_id)
        logging.info(f"tag_id found: {tag_id}")

        # Extract email from customer data

        customer = data.get('customer', {})

        #
        # Ensure async database calls are handled correctly
        async def async_process():
            # Find the item in the items collection
            item = await items_collection.find_one({'tag_id': tag_id})

            if item:
                update_fields = {}

                # Determine subscription status and tier
                if 'plan' in data and data['plan']:
                    update_fields['subscription_status'] = 'active'
                    update_fields['tier'] = data['plan'].get('name', item.get('tier', ''))
                else:
                    update_fields['subscription_status'] = 'one-time'
                    amount = data.get('amount', 0) / 100
                    update_fields['tier'] = 'Basic' if amount == 250 else 'Premium' if amount == 500 else 'Standard'

                # Update the item in the items collection
                await items_collection.update_one({'_id': item['_id']}, {'$set': update_fields})

                # Update the email address in the items collection
                email = customer.get('email')
                if email:
                    await items_collection.update_one({'_id': item['_id']}, {'$set': {'email_address': email}})
                else:
                    email = item.get('email_address')

                # Fetch the updated item
                updated_item = await items_collection.find_one({'_id': item['_id']})

                # Remove the '_id' field before embedding it in the user's items
                if '_id' in updated_item:
                    del updated_item['_id']

                uuid = item.get('uuid')
                logging.info(f"uuid found: {uuid}")
                if uuid:
                    # Find the user in the users collection
                    user = await users_collection.find_one({'uuid': uuid})
                    if user:
                        user_items = user.get('items', {})
                        # Ensure keys are strings
                        user_items = {str(k): v for k, v in user_items.items()}
                        logging.info(f"user_items keys: {list(user_items.keys())}")

                        if tag_id in user_items:
                            # Update the entire item under the user's items
                            result = await users_collection.update_one(
                                {'_id': user['_id']},
                                {'$set': {f'items.{tag_id}': updated_item}}
                            )
                            logging.info(f"Updated user item for tag {tag_id} to match items collection.")
                            logging.debug(f"Update result: {result.raw_result}")
                        else:
                            logging.warning(f"Tag {tag_id} not found in user's items.")
                    else:
                        logging.warning(f"User with uuid {uuid} not found.")

                    cleaned_email = clean_email(email)
                    logging.info(f"your cleaned mail is{cleaned_email}")

                    # Add the email sending task to the background tasks
                    background_tasks.add_task(send_email_webhook, cleaned_email)

        # Run async function in the background task
        anyio.from_thread.run(async_process)

    except Exception as e:
        logging.error(f"Error processing Paystack event: {str(e)}")

# Utility functions
