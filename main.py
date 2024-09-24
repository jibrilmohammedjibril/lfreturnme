import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Form, UploadFile, File, BackgroundTasks, Request
from datetime import datetime, timedelta
from firebase_admin import storage
from pydantic import EmailStr
import schemas
import crud
import uuid
from schemas import ItemRegistration, LostFound
from crud import get_tag_by_tag1, update_tag, save_item_registration, update_user_items, upload_to_firebase, send_email
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import logging
import time
from schemas import PaystackWebhookPayload
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib
import json


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)


@app.get("/")
async def root():
    return {"message": "Welcome to LFReturnMe API"}


@app.post("/signup/", response_model=schemas.ResponseSignup)
async def signup(
        full_name: str = Form(...),
        email_address: str = Form(...),
        date_of_birth: str = Form(...),
        address: str = Form(...),
        id_no: str = Form(...),
        phone_number: str = Form(...),
        gender: str = Form(...),
        valid_id_type: str = Form(...),
        password: str = Form(...),
        profile_picture: UploadFile = File(...),
        id_card_image: UploadFile = File(...)
):
    try:
        date_of_birth_obj = datetime.strptime(date_of_birth, "%Y-%m-%d").date()

        # Upload files to Firebase
        profile_picture_url = upload_to_firebase(profile_picture)
        id_card_image_url = upload_to_firebase(id_card_image)

        user = schemas.Signup(
            full_name=full_name,
            email_address=email_address,
            date_of_birth=date_of_birth_obj,
            address=address,
            id_no=id_no,
            phone_number=phone_number,
            gender=gender,
            valid_id_type=valid_id_type,
            profile_picture=profile_picture_url,
            id_card_image=id_card_image_url,
            password=password,
            is_verified=False,

        )

        db_user = await crud.create_user(user=user)
        if db_user:
            return db_user
        else:
            raise HTTPException(status_code=400, detail="Email address already exists")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {ve}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/signin/", response_model=schemas.ResponseSignup)
async def signin(user: schemas.Signin):
    try:
        user.email_address = user.email_address.lower()
        db_user = await crud.authenticate_user(user.email_address, user.password)
        return db_user
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/register-item/")
async def register_item(
        item_id: str = Form(...),
        item_type: str = Form(...),
        item_name: str = Form(...),
        tag_id: str = Form(...),
        item_image: UploadFile = File(...),
        item_description: str = Form(...),
        uuid: str = Form(...),

):
    tag = await get_tag_by_tag1(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    if tag.is_owned:
        raise HTTPException(status_code=400, detail="This tag is already owned")

    # Upload image to Firebase
    image_url = upload_to_firebase(item_image)

    now = datetime.now()
    date_string = now.strftime("%Y-%m-%d")
    registered_date_obj = datetime.strptime(date_string, "%Y-%m-%d").date()
    registered_date_str = registered_date_obj.strftime("%Y-%m-%d")

    # Save item registration
    item = ItemRegistration(
        item_id=item_id,
        item_type=item_type,
        item_name=item_name,
        tag_id=tag_id,
        item_image=image_url,  # Save the image URL
        item_description=item_description,
        uuid=uuid,
        registered_date=registered_date_str,
        status="0"
    )

    if not await save_item_registration(item):
        raise HTTPException(status_code=500, detail="Failed to save item registration")

    if not await update_user_items(uuid, item):
        raise HTTPException(status_code=500, detail="Failed to update user's items")

    if not await update_tag(tag_id, uuid):
        raise HTTPException(status_code=500, detail="Failed to update the tag")

    return {"message": "Item registered successfully"}


@app.post("/forgot-password/")
async def forgot_password(request: schemas.ForgotPasswordRequest):
    try:
        token = await crud.create_reset_token(request.email_address)
        if token:
            reset_link = f"https://lfreturnme.com/reset-password/{token}. Link  expires after 5 minutes"
            send_email_reset(request.email_address, reset_link)
            return {"message": "Password reset email sent"}
        else:
            raise HTTPException(status_code=404, detail="Email address not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/reset-password/")
async def reset_password(request: schemas.ResetPasswordRequest):
    try:
        email_address = await crud.validate_reset_token(request.token)
        if email_address:
            success = await crud.update_password(email_address, request.new_password)
            if success:
                return {"message": "Password reset successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to reset password")
        else:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


def send_email_reset(to_email: str, reset_link: str):
    msg = MIMEText(f"Click the link to reset your password: {reset_link}")
    msg['Subject'] = 'Password Reset Request'
    msg['From'] = 'no_reply@lfreturnme.com'
    msg['To'] = to_email
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")
    sender_host = os.getenv("EMAIL_HOST")

    try:
        with smtplib.SMTP_SSL(sender_host, 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail("infonfo@lfreturnme.com", to_email, msg.as_string())
            print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


# Assuming `client` and `database` are already defined as in your existing code


@app.put("/update-item-status/")
async def update_item_status(
        uuid: str = Query(..., title="UUID of the user"),
        tagid: str = Query(..., title="Tag ID / Item ID to find"),
        new_status: str = Query(..., title="New status (integer) to update")
):
    return await crud.update_item_status_full(uuid, tagid, new_status, crud.users_collection, crud.items_collection)


@app.post("/email-sub/", response_model=dict)
async def subscribe_newsletter(newsletter_email: schemas.NewsletterEmail):
    try:
        success = await crud.add_newsletter_email(newsletter_email.email)
        if not success:
            raise HTTPException(status_code=400, detail="Email already subscribed")
        return {"message": "Email subscribed successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


lf_email = "info@lfreturnme.com"


@app.post("/lost/")
async def add_lost_item(
        item: str = Form(...),
        name: str = Form(...),
        location: str = Form(...),
        phone_number: str = Form(...),
        email: EmailStr = Form(...),
        description: str = Form(...),
        item_image: UploadFile = File(None),  # Make item_image optional,
        tag_id: Optional[str] = Form(None),
):
    start_time = time.time()
    image_url = ""
    if item_image is not None:
        image_url = upload_to_firebase(item_image)

    logging.info(f"Time taken for file upload: {time.time() - start_time} seconds")

    now = datetime.now()
    date_string = now.strftime("%Y-%m-%d")
    registered_date_obj = datetime.strptime(date_string, "%Y-%m-%d").date()
    registered_date_str = registered_date_obj.strftime("%Y-%m-%d")

    lost = LostFound(
        item=item,
        name=name,
        location=location,
        date=registered_date_str,
        phone_number=phone_number,
        email=email,
        description=description,
        item_image=image_url,
        tag_id=tag_id  # Assuming tag_id is part of the form or set to None
    )

    if lost.tag_id is None:
        # Add to lost collection
        await crud.add_to_lost(lost)
        # send mail to the person that lost it
        logging.info(f"Time taken for adding to lost collection: {time.time() - start_time} seconds")
        send_email(to_email=lost.email,
                   subject="Item Lost",
                   body=f" Dear {lost.name}, you have reported item your lost."
                   )
        # Send email to lfreturme
        send_email(lf_email, "reported  Lost item",
                   f"item {lost.item} has been reported lost at {lost.location}, this item is not registered and the person that lost is {lost.name}")

        logging.info(f"Time taken for sending emails: {time.time() - start_time} seconds")

        return JSONResponse(status_code=200, content={"message": "Item added to lostfound and email sent"})
    else:
        # Search items collection by tag_id
        item = await crud.find_item_by_tag_id(lost.tag_id)
        logging.info(f"Time taken for finding item by tag_id: {time.time() - start_time} seconds")
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")

        # Retrieve user information by uuid
        user = await crud.find_user_by_uuid(item.uuid)
        logging.info(f"Time taken for finding user by uuid: {time.time() - start_time} seconds")
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Update item status to lost using the update tag endpoint

        await crud.update_item_status_full(item.uuid, lost.tag_id, "2", crud.users_collection,
                                           crud.items_collection)
        logging.info(f"Time taken for updating item status: {time.time() - start_time} seconds")
        await crud.add_to_lost(lost)
        logging.info(f"Time taken for adding to lost collection: {time.time() - start_time} seconds")
        # Send email to user
        send_email(user["email_address"], "Item Lost",
                   f"You have reported {item.item_name} lost.")
        # send email to lfreturnme

        send_email(lf_email, "Item Lost",
                   f" registered item '{item.item_name}' has been reported lost.tit is registered")
        logging.info(f"Time taken for sending email to user: {time.time() - start_time} seconds")

        return JSONResponse(status_code=200, content={"message": "Item status updated and email sent to user"})


@app.post("/found/")
async def add_found_item(
        item: str = Form(...),
        name: str = Form(...),
        location: str = Form(...),
        phone_number: str = Form(...),
        email: EmailStr = Form(...),
        description: str = Form(...),
        item_image: UploadFile = File(None),
        tag_id: Optional[str] = Form(None),
):
    start_time = time.time()
    if item_image is not None:
        image_url = upload_to_firebase(item_image)
    else:
        image_url = ""
    now = datetime.now()
    date_string = now.strftime("%Y-%m-%d")
    registered_date_obj = datetime.strptime(date_string, "%Y-%m-%d").date()
    registered_date_str = registered_date_obj.strftime("%Y-%m-%d")

    found = LostFound(
        item=item,
        name=name,
        location=location,
        date=registered_date_str,
        phone_number=phone_number,
        email=email,
        description=description,
        item_image=image_url,
        tag_id=tag_id  # Assuming tag_id is part of the form or set to None
    )

    if found.tag_id is None:
        # Add to found collection
        await crud.add_to_found(found)
        # send mail to the person that lost it
        send_email(found.email,
                   "Item Found",
                   f"item your items  {found.name} has been reported found"
                   )
        # Send email to lfreturme
        send_email(lf_email,
                   "reported  Lost item",
                   f"item {found.item} has been reported found at {found.location},the item is not registered and the person that found is{found.name}")
        return JSONResponse(status_code=200, content={"message": "Item added to found and email sent"})
    else:
        # Search items collection by tag_id
        item = await crud.find_item_by_tag_id(found.tag_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")

        # Retrieve user information by uuid
        user = await crud.find_user_by_uuid(item.uuid)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Update item status to lost using the update tag endpoint

        await crud.update_item_status_full(item.uuid, found.tag_id, "1", crud.users_collection,
                                           crud.items_collection)
        await crud.add_to_found(found)
        # Send email to user
        send_email(user['email_address'], "Item Found", f"Your item {found.name} has been  found.")
        # send email to lfreturnme
        send_email(lf_email, "Item Found",
                   f"""{user["full_name"]}'s  registered item {item.item_name} has been reported found.""")

        return JSONResponse(status_code=200, content={"message": "Item status updated and email sent to user"})


@app.put("/update-profile/")
async def update_profile(
        user_uuid: str = Form(...),
        full_name: str = Form(...),
        email_address: str = Form(...),
        address: str = Form(...),
        profile_picture: UploadFile = File(None)
):
    # Retrieve the current user profile from MongoDB
    user = await crud.get_user_by_uuid(user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Extract current profile picture URL if it exists
    current_picture_url = user.get("profile_picture")

    # Handle the profile picture upload if provided
    profile_picture_url = upload_to_firebase(profile_picture) if profile_picture else current_picture_url

    # Create the update data dictionary
    update_data = {
        "full_name": full_name,
        "email_address": email_address,
        "address": address,
        "profile_picture": profile_picture_url
    }

    # Perform the update operation
    result = await crud.update_user_profile(user_uuid, update_data)

    if current_picture_url:
        crud.delete_from_firebase(current_picture_url)
    # Check if the update was successful
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User profile updated successfully"}


@app.post("/api/send-otp")
async def send_otp(request: schemas.OTPRequest):
    otp = crud.generate_otp()
    crud.send_email_otp(request.email, otp)

    otp_data = {
        "email": request.email,
        "otp": otp,
        "timestamp": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=5)
    }
    crud.otp_collection.insert_one(otp_data)

    return {"message": "OTP sent successfully to your email."}  # Remove OTP from response in production


# API endpoint to verify OTP
@app.post("/api/verify-otp")
async def verify_otp(request: schemas.OTPVerify):
    # Find the OTP entry in the collection
    otp_entry = await crud.otp_collection.find_one({"email": request.email, "otp": request.otp})

    if not otp_entry:
        raise HTTPException(status_code=404, detail="Invalid OTP or email")

    # Check if the OTP has expired
    if datetime.utcnow() > otp_entry['expires_at']:
        # Delete the expired OTP
        await crud.otp_collection.delete_one({"_id": otp_entry['_id']})
        raise HTTPException(status_code=400, detail="OTP has expired")

    # OTP is valid, proceed to verify the user's email
    await crud.verify_user_email(request.email)

    # Delete the OTP after successful verification
    await crud.otp_collection.delete_one({"_id": otp_entry['_id']})

    return {"message": "OTP verified successfully"}


@app.get("/dashboard/{uuid}", response_model=schemas.ResponseSignup)
async def get_user_dashboard(uuid: str):
    user = await crud.db["users"].find_one({"uuid": uuid})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    items = user.get("items", {})

    # Convert MongoDB user document to ResponseSignup model
    user_data = schemas.ResponseSignup(
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
        items=user.get("items", {})  # Assuming items are stored as a dictionary
    )

    return user_data


@app.get("/subscriptions/update")
async def fetch_and_update_subscriptions(background_tasks: BackgroundTasks):
    active_subscriptions = await crud.get_active_subscriptions()

    # Fetch details and update each subscription
    for sub in active_subscriptions:
        subscription_code = sub['subscription_code']
        tier = sub['plan']['name']  # Assuming 'plan' contains the subscription tier
        status = sub['status']  # Assuming 'status' holds the subscription status

        # Update the user's subscription status and tier
        background_tasks.add_task(crud.update_user_subscription, subscription_code, status, tier)

    return {"message": "Subscriptions update process started."}


# Paystack Webhook to update subscription status
# @app.post("/webhook")
# async def paystack_webhook(request: Request):
#     #payload = await request.json()
#     try:
#         body = await request.body()  # Read raw body
#         if not body:
#             raise HTTPException(status_code=400, detail="Empty body in the request.")

#         payload = await request.json()  # Parse JSON if body is not empty
#     except ValueError:
#         raise HTTPException(status_code=400, detail="Invalid JSON in request body.")
#     logging.info(payload)
#     print(payload)
#     # event = payload.get("event")
#     # subscription_code = payload["data"]["subscription_code"]

#     # if event in ["subscription.disable", "subscription.expired"]:
#     #     # Handle subscription cancellation
#     #     await crud.update_user_subscription(subscription_code, "inactive", None)
#     #     return {"message": "Subscription marked as inactive"}

#     # elif event in ["subscription.create", "subscription.enable"]:
#     #     # Handle subscription creation or reactivation
#     #     tier = payload["data"]["plan"]["name"]
#     #     await crud.update_user_subscription(subscription_code, "active", tier)
#     #     return {"message": "Subscription marked as active"}

#     return {"message": "Event not processed"}

# # @app.post("/my/webhook/url")
# # async def webhook(request: Request):
# #     # Retrieve the request's body
# #     payload = await request.json()  # Similar to req.body in Express
# #     # Do something with the event (payload)
# #     return {"message": "Webhook received"}, 200  # Send HTTP 200 response


# @app.post("/paystack-webhook")
# async def paystack_webhook(payload:PaystackWebhookPayload):
#     logging.info(payload)
#     #if payload.event == "charge.success":
#     #    payment_data = payload.data
#         # Do something with payment data
#         # Example: Save payment data to database, send email to customer, update order status, etc.
#         #return {"message":"Payment successful"} # redirect to a payment succesful page
#     return {"message":"Payment failed"} # can also redirect users to a page to try again or contact support

PAYSTACK_SECRET_KEY = "sk_test_94963cced904b3899da00773517d076436e5397d"

# Helper function to verify Paystack signature
def verify_paystack_signature(request_body: str, received_signature: str) -> bool:
    computed_signature = hmac.new(
        PAYSTACK_SECRET_KEY.encode("utf-8"),
        request_body.encode("utf-8"),
        hashlib.sha512
    ).hexdigest()

    return hmac.compare_digest(computed_signature, received_signature)

@app.post("/webhook/paystack")
async def paystack_webhook(request: Request):
    # Get the request body
    payload = await request.body()

    # Paystack sends a header 'x-paystack-signature' for webhook validation
    paystack_signature = request.headers.get('x-paystack-signature')

    # Verify the signature
    if not verify_paystack_signature(payload.decode("utf-8"), paystack_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Parse the JSON payload
    event = json.loads(payload)

    # Check the event type (subscription, payment, etc.)
    if event["event"] == "subscription.create":
        # Handle subscription creation
        print(f"New subscription created: {event['data']['subscription_code']}")

    elif event["event"] == "charge.success":
        # Handle successful payment
        print(f"Payment successful: {event['data']['reference']}")

    # Handle other event types as necessary
    elif event["event"] == "subscription.disable":
        # Handle subscription disabled event
        print(f"Subscription disabled: {event['data']['subscription_code']}")

    return {"status": "success"}
