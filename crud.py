import asyncio
import base64
import json
import os
import re
import random
import httpx
import motor.motor_asyncio
from fastapi import UploadFile, HTTPException, BackgroundTasks
import schemas
import uuid
import bcrypt
import logging
from schemas import Tag, ItemRegistration
from bson import ObjectId
import firebase_admin
from firebase_admin import credentials, storage
from typing import Optional
from datetime import datetime, timedelta
from pymongo import ReturnDocument
from dotenv import load_dotenv
import hmac
import hashlib
import schedule
import time

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
access_collection = db['access']

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
                #"id_no": user.id_no,
                "profile_picture": user.profile_picture,
                "phone_number": user.phone_number,
                "gender": user.gender,
                #"valid_id_type": user.valid_id_type,
                #"id_card_image": user.id_card_image,
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

            # Generate access token using save_access_token function
            access_token = await save_access_code(user.get("uuid"))  # Assuming this function generates a token

            # Update user with access_token and return updated schema
            return schemas.ResponseSignup(
                uuid=user.get("uuid"),
                full_name=user.get("full_name"),
                email_address=user.get("email_address"),
                date_of_birth=user.get("date_of_birth"),
                address=user.get("address"),
                id_no=user.get("id_no"),
                profile_picture=user.get("profile_picture"),
                phone_number=user.get("phone_number"),
                gender=user.get("gender"),
                valid_id_type=user.get("valid_id_type"),
                id_card_image=user.get("id_card_image"),
                password=user.get("password"),
                is_verified=user.get("is_verified"),
                access_token=access_token,  # Adding the generated access_token here
                items=user.get("items", {})  # Default to empty dict if items not present
            )
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

        #if user_result.modified_count == 0:
        #   raise HTTPException(status_code=500, detail="Failed to update item status in user's items")

        # Find item in the items collection by tagid
        item = await items_collection.find_one({"tag_id": tagid})
        if not item:
            raise HTTPException(status_code=404, detail="Item not found in items collection")

        # Update the item's status in the items collection
        item_result = await items_collection.update_one(
            {"tag_id": tagid},
            {"$set": {"status": new_status}}
        )

        #if item_result.modified_count == 0:
        #    raise HTTPException(status_code=500, detail="Failed to update item status in items collection")

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


from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os


def send_email(to_email: str, subject: str, body_content: str):
    # Create a multipart email (text and HTML)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = 'lostfound_no_reply@lfreturnme.com'
    msg["To"] = to_email

    # Define the plain text version of the email content
    plain_text = f"""
    {body_content}

    Best regards,
    LFReturnMe Team

    -- 
    LFReturnMe
    Phone: (123) 456-7890
    Website: www.lfreturnme.com
    """

    # Define the HTML version of the email content
    html_body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                -webkit-font-smoothing: antialiased;
                -moz-osx-font-smoothing: grayscale;
            }}
            .email-container {{
                max-width: 600px;
                margin: 20px auto;
                background-color: #ffffff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            }}
            .email-header {{
                text-align: center;
                padding-bottom: 20px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .email-header img {{
                width: 120px;
            }}
            .email-body {{
                padding: 20px;
                color: #333333;
                line-height: 1.6;
            }}
            .email-body h2 {{
                color: #333;
            }}
            .email-footer {{
                text-align: center;
                padding: 20px;
                color: #999999;
                border-top: 1px solid #e0e0e0;
            }}
            .social-icons {{
                margin: 10px 0;
            }}
            .social-icons img {{
                width: 24px;
                margin: 0 10px;
                vertical-align: middle;
            }}
            a {{
                color: #007BFF;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <img src="https://res.cloudinary.com/dskwy11us/image/upload/v1727959923/logo2_4_1_usow6b.png" alt="LFReturnMe Logo">
            </div>
            <div class="email-body">
                {body_content}
                <p>Best regards,<br><strong>LFReturnMe Team</strong></p>
            </div>
            <div class="email-footer">
                <p>Connect with us on social media:</p>
                <div class="social-icons">
                    <a href="https://www.instagram.com/lfreturnme" target="_blank">
                        <img src="https://cdn-icons-png.flaticon.com/512/2111/2111463.png" alt="Instagram">
                    </a>
                    <a href="https://twitter.com/LFReturnMe1" target="_blank">
                        <img src="https://cdn-icons-png.flaticon.com/512/733/733579.png" alt="Twitter">
                    </a>
                    <a href="https://www.linkedin.com/company/lfreturnme" target="_blank">
                        <img src="https://cdn-icons-png.flaticon.com/512/174/174857.png" alt="LinkedIn">
                    </a>
                    <a href="https://www.facebook.com/LFReturnMe" target="_blank">
                        <img src="https://cdn-icons-png.flaticon.com/512/733/733547.png" alt="Facebook">
                    </a>
                </div>
                <p>&copy; {str(datetime.now().year)} LFReturnMe. All rights reserved.</p>
                <p>Phone: (123) 456-7890 | Website: <a href="https://www.lfreturnme.com">www.lfreturnme.com</a></p>
            </div>
        </div>
    </body>
    </html>
    """

    # Attach the plain text and HTML versions of the body
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Email server configuration
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")
    sender_host = os.getenv("EMAIL_HOST")

    # Sending the email
    with smtplib.SMTP_SSL(sender_host, 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        print("Email sent successfully!")


# Example usage


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

    # Remove everything after '+' including the '+' itself
    cleaned_prefix = re.sub(r'\+\d+', '', prefix)

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


# Define the function that retrieves the subscription code from the Paystack API
async def get_subscription_code(customer_email: str) -> str:
    paystack_secret_key = os.getenv("PAYSTACK_SECRET_KEY")
    url = f"https://api.paystack.co/customer/{customer_email}"

    headers = {
        "Authorization": f"Bearer {paystack_secret_key}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            # Extract the subscription_code if available
            subscriptions = data.get("data", {}).get("subscriptions", [])
            if subscriptions:
                return subscriptions[0].get("subscription_code", "No subscription found")
            else:
                return "No subscription found"
        else:
            return f"Failed to retrieve customer data: {response.text}"
    except Exception as e:
        return f"An error occurred: {str(e)}"


def extract_numbers_and_next_payment_date(data: dict) -> tuple[None, None, str]:
    # Extract the email from the 'customer' field in the data
    email = data.get('customer', {}).get('email', '')

    # Extract the next payment date from the data
    next_payment_date = data.get('next_payment_date', None)

    # Use a regular expression to match the numbers between '+' and '@' in the email
    match = re.search(r'\+(\d+)\@', email)

    if match:
        # Return the matched numbers and the next payment date
        return match.group(1), next_payment_date, email
    else:
        # Return None for the numbers and next payment date if no match is found
        return None, next_payment_date, email


async def process_paystack_event(data: dict, event_type: str, background_tasks: BackgroundTasks):
    logging.info(f"Processing Paystack event with data: {data} and event_type: {event_type}")

    try:
        # Initialize variables
        tag_id = None
        email = None

        if event_type == "subscription.not_renew":
            tag_id, next_payment_date, email = extract_numbers_and_next_payment_date(data)
        else:
            # Extract metadata and custom_fields
            metadata = data.get('metadata', {})
            custom_fields = metadata.get('custom_fields', [])
            logging.info(f"Metadata: {metadata}")
            logging.info(f"Custom fields: {custom_fields}")

            # Extract the tag_id from custom_fields
            tag_id = next((field.get('value') for field in custom_fields if field.get('variable_name') == 'tag_id'),
                          None)
            customer = data.get('customer', {})
            email = customer.get('email')

        if not tag_id:
            logging.warning("tag_id not found")
            return

        # Ensure tag_id is a string
        tag_id = str(tag_id)
        logging.info(f"tag_id found: {tag_id}")

        await async_process(event_type, tag_id, email, data, background_tasks)

    except Exception as e:
        logging.error(f"Error processing Paystack event: {str(e)}")


async def async_process(event_type, tag_id, email, data, background_tasks):
    try:
        # Find the item in the items collection
        item = await items_collection.find_one({'tag_id': tag_id})

        if item:
            update_fields = {}

            # Process based on event type
            if event_type == 'charge.success':
                if 'plan' in data and data['plan']:
                    update_fields['subscription_status'] = 'active'
                    update_fields['tier'] = data['plan'].get('name', item.get('tier', ''))
                    update_fields["subscription_code"] = await get_subscription_code(email)
                else:
                    update_fields['subscription_status'] = 'one-time'
                    amount = data.get('amount', 0) / 100
                    update_fields['tier'] = (
                        'Basic' if amount == 250 else
                        'Premium' if amount == 1000 else
                        'Standard' if amount == 300 else
                        "Passport" if amount == 1500 else
                        "super standard"
                    )

                if email:
                    update_fields['email_address'] = email
                else:
                    email = item.get('email_address')  # Retrieve from item if not in customer

            elif event_type == "subscription.not_renew":
                logging.info("Subscription not renewed")
                next_payment_date_str = data.get('next_payment_date')
                if next_payment_date_str:
                    # Parse the next_payment_date from string to datetime
                    subscription_end = datetime.strptime(next_payment_date_str, "%Y-%m-%d")
                    update_fields['subscription_end'] = subscription_end
                else:
                    logging.warning("next_payment_date not found in data")
                    update_fields['subscription_end'] = datetime.now()  # Default to now

            elif event_type == 'subscription.disable':
                update_fields['subscription_status'] = 'cancelled'
                update_fields['subscription_end'] = datetime.now()

            else:
                logging.info(f"Unhandled event type: {event_type}")
                return

            # Update the item in the items collection
            await items_collection.update_one({'_id': item['_id']}, {'$set': update_fields})

            # Fetch the updated item
            updated_item = await items_collection.find_one({'_id': item['_id']})
            if '_id' in updated_item:
                del updated_item['_id']

            uuid = item.get('uuid')
            logging.info(f"uuid found: {uuid}")
            if uuid:
                # Find the user in the users collection
                user = await users_collection.find_one({'uuid': uuid})
                if user:
                    user_items = user.get('items', {})
                    user_items = {str(k): v for k, v in user_items.items()}

                    if tag_id in user_items:
                        await users_collection.update_one(
                            {'_id': user['_id']},
                            {'$set': {f'items.{tag_id}': updated_item}}
                        )
                        logging.info(f"Updated user item for tag {tag_id} to match items collection.")
                    else:
                        logging.warning(f"Tag {tag_id} not found in user's items.")
                else:
                    logging.warning(f"User with uuid {uuid} not found.")

            # Ensure email is available before proceeding
            if email:
                cleaned_email = clean_email(email)
                logging.info(f"Cleaned email: {cleaned_email}")

                # Add email sending task to background tasks
                background_tasks.add_task(send_email_webhook, cleaned_email)
            else:
                logging.warning("No email found for this transaction.")
    except Exception as e:
        logging.error(f"Error inside async_process: {str(e)}")


async def generate_code():
    return str(random.randint(1000000000, 9999999999))  # Generate 10-digit code


async def save_access_code(uuid: str):
    current_time = datetime.utcnow()

    # Search for existing code with the same uuid
    existing_record = await access_collection.find_one({"uuid": uuid})

    if existing_record:
        # Check if the existing code was generated within the last 15 minutes
        last_timestamp = existing_record["timestamp"]
        if current_time - last_timestamp < timedelta(minutes=15):
            # Return existing code if within 15 minutes
            return existing_record["code"]

        # Delete the existing record if it's older than 15 minutes
        await access_collection.delete_one({"uuid": uuid})

    # Generate new code and save to MongoDB
    new_code = await generate_code()
    await access_collection.insert_one({
        "uuid": uuid,
        "code": new_code,
        "timestamp": current_time
    })

    return new_code


async def update_expired_subscriptions(items_collection, users_collection):
    current_date = datetime.now()

    # Find items with expired subscriptions
    expired_items = await items_collection.find(
        {"subscription_end": {"$lt": current_date}, "subscription_status": "active"}).to_list(length=None)
    print(expired_items)
    for item in expired_items:
        item_id = item['item_id']
        tag_id = item['tag_id']
        user_uuid = item['uuid']
        logging.info(f"modifying {user_uuid} and tag {tag_id}")
        # Update the item's subscription status to inactive in the items collection
        await items_collection.update_one({"item_id": item_id}, {"$set": {"subscription_status": "inactive"}})

        # Update the corresponding item status to inactive in the user's collection
        await users_collection.update_one(
            {"uuid": user_uuid, "items.tag_id": tag_id},
            {"$set": {"items.$.status": "inactive"}}
        )
