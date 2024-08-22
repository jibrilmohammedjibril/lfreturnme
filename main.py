import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Form, UploadFile, File, BackgroundTasks
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
    user = await  crud.get_user_by_uuid(user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Extract current profile picture URL if exists
    current_picture_url = user.get("profile_picture")

    # Create the update data dictionary
    update_data = {
        "full_name": full_name,
        "email_address": email_address,
        "address": address
    }

    # Handle the profile picture upload if provided
    if profile_picture:
        # Delete the old profile picture from Firebase Storage if it exists
        if current_picture_url:
            crud.delete_from_firebase(current_picture_url)

        # Upload the new file directly to Firebase Storage
        profile_picture_url = upload_to_firebase(profile_picture)
        update_data["profile_picture"] = profile_picture_url

    # Perform the update operation
    result = await crud.update_user_profile(user_uuid, update_data)

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
    otp_entry = await crud.otp_collection.find_one({"email": request.email, "otp": request.otp})

    if not otp_entry:
        raise HTTPException(status_code=404, detail="Invalid OTP or email")

    if datetime.utcnow() > otp_entry['expires_at']:
        await crud.otp_collection.delete_one({"_id": otp_entry['_id']})
        await crud.verify_user_email(request.email)
        raise HTTPException(status_code=400, detail="OTP has expired")

    # OTP is valid, proceed with your operation and then delete the OTP
    await crud.otp_collection.delete_one({"_id": otp_entry['_id']})
    return {"message": "OTP verified successfully"}
