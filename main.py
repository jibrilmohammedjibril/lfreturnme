import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Form, UploadFile, File, BackgroundTasks, Request
from datetime import datetime, timedelta
from pydantic import EmailStr
import schemas
import crud
from schemas import ItemRegistration, LostFound
from crud import get_tag_by_tag1, update_tag, save_item_registration, update_user_items, upload_to_firebase, send_email
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import logging
import time
from fastapi import FastAPI, Request, HTTPException
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from crud import update_subscriptions_daily  # Import the function from crud.py

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
scheduler = AsyncIOScheduler()

logging.basicConfig(level=logging.INFO)


async def scheduled_task():
    await update_subscriptions_daily(crud.items_collection, crud.users_collection)


# Schedule the task to run every day at midnight
#scheduler.add_job(scheduled_task, 'cron', hour=0, minute=0)
scheduler.add_job(scheduled_task, 'interval', minutes=1)


@app.on_event("startup")
async def startup_event():
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()


@app.get("/")
async def root():
    return {"message": "Welcome to LFReturnMe API"}


@app.get("/schedule-task")
async def run_task(background_tasks: BackgroundTasks):
    background_tasks.add_task(scheduled_task)
    return {"message": "Task scheduled"}


@app.post("/signup/", response_model=schemas.ResponseSignup)
async def signup(
        full_name: str = Form(...),
        email_address: str = Form(...),
        date_of_birth: str = Form(...),
        address: str = Form(...),
        phone_number: str = Form(...),
        gender: str = Form(...),
        password: str = Form(...),
        profile_picture: UploadFile = File(...),

):
    try:
        date_of_birth_obj = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        email_address = email_address.lower()

        # Upload files to Firebase
        profile_picture_url = upload_to_firebase(profile_picture)
        #id_card_image_url = upload_to_firebase(id_card_image)

        user = schemas.Signup(
            full_name=full_name,
            email_address=email_address,
            date_of_birth=date_of_birth_obj,
            address=address,
            #id_no=id_no,
            phone_number=phone_number,
            gender=gender,
            #valid_id_type=valid_id_type,
            profile_picture=profile_picture_url,
            #id_card_image=id_card_image_url,
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
        email_address_ = await crud.validate_reset_token(request.token)
        email_address = email_address_.lower()
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
        background_tasks: BackgroundTasks,
        uuid: str = Query(..., title="UUID of the user"),
        tagid: str = Query(..., title="Tag ID / Item ID to find"),
        new_status: str = Query(..., title="New status (integer) to update")
):
    if new_status == "1":
        user = await crud.find_user_by_uuid(uuid)
        item = await crud.find_item_by_tag_id(tagid)
        background_tasks.add_task(
            send_email,
            user["email_address"],
            f"Your {item.item_name} is Now Reported as Lost",
            f"""
                <h2>Dear {user['full_name']},</h2>
            
                <p>We’re sorry to hear that you’ve misplaced your <strong>{item.item_description}</strong>. Rest assured, LFReturnMe is here to help you in your efforts to recover it!</p>
            
                <p>Your item has now been marked as lost in our system, and we will notify members of our Finders Community to be on the lookout.</p>
            
                <h3>Next Steps:</h3>
                <ul>
                    <li><strong>Track Updates:</strong> We’ll keep you informed if any updates or reports come in regarding your lost item.</li>
                    <li><strong>Spread the Word:</strong> You can also share your lost item details with your network, and encourage others to join our Finders Community to increase your chances of recovery.</li>
                    <li><strong>Recovery Process:</strong> If your item is found, we’ll notify you immediately with instructions on how to claim it.</li>
                </ul>
            
                <p>If you have any questions or need further assistance, feel free to reach out to our support team. We’re with you every step of the way!</p>
            """
        )

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
        send_email(lost.email,
                   "We've Received Your Lost Item Report",
                   f"""
                       <h2>Dear {lost.name},</h2>

                       <p>Thank you for trusting LFReturnMe to help you recover your lost <strong>{lost.description}</strong>. Our Finders Community is now on alert, and we will do our best to assist you in locating your item.</p>

                       <h3>Here’s what happens next:</h3>
                       <ul>
                           <li><strong>Item Registration:</strong> Your lost item has been added to our system, and we’re actively monitoring for any reports from our Finders Community.</li>
                           <li><strong>Notifications:</strong> If someone reports finding an item matching your description, you will be notified immediately with further instructions.</li>
                           <li><strong>Spread the Word:</strong> You can increase your chances by sharing the details of your lost item with your friends, family, or social media. We’re also working on expanding our Finders Network to help connect people faster.</li>
                       </ul>

                       <p><strong>Need extra help?</strong> If you’d like to benefit from additional recovery services, feel free to explore our subscription plans <a href="[link to plans]">here</a>, which offer enhanced recovery support, priority notifications, and more.</p>

                       <p>For any questions or assistance, don’t hesitate to contact us at [support email or phone number].</p>
                   """)
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

        await crud.update_item_status_full(item.uuid, lost.tag_id, "1", crud.users_collection,
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
        background_tasks: BackgroundTasks,
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

        # Send thank-you email to the person who found the item
        background_tasks.add_task(
            send_email,
            found.email,
            "Thank You for Reporting a Found Item on LFReturnMe",
            f"""
            <h2>Thank You for Reporting a Found Item!</h2>
            <p>Dear {found.name},</p>
            <p>We are thrilled to receive your report about the <strong>{found.description}</strong> you found! Thank you for playing an 
            important role in reconnecting lost items with their rightful owners. Your contribution makes a real difference.</p>
            <p>Our team is actively working on matching the found item with its owner. We’ll keep you updated on the next steps.</p>
            <h3>What happens next:</h3>
            <ul>
                <li>If the owner of the item claims it, we’ll facilitate the recovery process through our platform.</li>
                <li>Should the owner wish to express their gratitude, there may be a small token of appreciation sent your way.</li>
            </ul>
            <p>In the meantime, thank you for being an amazing part of our Finders Community! If you have any questions or concerns, feel free to contact us.</p>
            """
        )

        # Send email to LFReturnMe team
        background_tasks.add_task(
            send_email,
            lf_email,
            "Item found with a tag",
            f"""Item {found.item} has been found at {found.location}. 
            The item is a {found.description}, reported by {found.name}. 
            The finder's contacts are {found.phone_number} and {found.email}."""
        )

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
        await crud.update_item_status_full(item.uuid, found.tag_id, "2", crud.users_collection, crud.items_collection)
        await crud.add_to_found(found)

        # Send email to LFReturnMe team
        background_tasks.add_task(
            send_email,
            lf_email,
            "Item found with a tag",
            f"""Item {found.item} has been found at {found.location}. 
            The item is a {found.description}, the tag ID is {found.tag_id}, reported by {found.name}. 
            The finder's contacts are {found.phone_number} and {found.email}."""
        )

        # Send thank-you email to the finder
        background_tasks.add_task(
            send_email,
            found.email,
            "Thank You for Reporting a Found Item on LFReturnMe",
            f"""
            <h2>Thank You for Reporting a Found Item!</h2>
            <p>Dear {found.name},</p>
            <p>We are thrilled to receive your report about the <strong>{found.description}</strong> you found! Thank you for playing an 
            important role in reconnecting lost items with their rightful owners. Your contribution makes a real difference.</p>
            <p>Our team is actively working on matching the found item with its owner. We’ll keep you updated on the next steps.</p>
            <h3>What happens next:</h3>
            <ul>
                <li>If the owner of the item claims it, we’ll facilitate the recovery process through our platform.</li>
                <li>Should the owner wish to express their gratitude, there may be a small token of appreciation sent your way.</li>
            </ul>
            <p>In the meantime, thank you for being an amazing part of our Finders Community! If you have any questions or concerns, feel free to contact us.</p>
            """
        )

        return JSONResponse(status_code=200,
                            content={"message": "Item status updated and emails sent to user and finder"})


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
    # Find the user by uuid
    user = await crud.db["users"].find_one({"uuid": uuid})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Call the function to generate or retrieve the access token
    access_token = await crud.save_access_code(uuid)

    # Convert MongoDB user document to ResponseSignup model
    user_data = schemas.ResponseSignup(
        uuid=user.get("uuid"),
        full_name=user.get("full_name"),
        email_address=user.get("email_address"),
        date_of_birth=user.get("date_of_birth"),
        address=user.get("address"),
        #id_no=user.get("id_no"),
        profile_picture=user.get("profile_picture"),
        phone_number=user.get("phone_number"),
        gender=user.get("gender"),
        #valid_id_type=user.get("valid_id_type"),
        #id_card_image=user.get("id_card_image"),
        password=user.get("password"),
        is_verified=user.get("is_verified"),
        items=user.get("items", {})  # Assuming items are stored as a dictionary
    )

    # Add the access token to the response data
    response_data = user_data.dict()
    response_data["access_token"] = access_token

    return response_data


@app.post("/webhook/paystack")
async def paystack_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        # Get the raw request body
        payload = await request.body()
        logging.info(payload)

        # Log the payload for debugging
        logging.debug(f"Received payload: {payload.decode('utf-8')}")

        # Paystack sends a header 'x-paystack-signature' for webhook validation
        paystack_signature = request.headers.get('x-paystack-signature')

        # Verify the signature
        if not crud.verify_paystack_signature(payload.decode("utf-8"), paystack_signature):
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Parse the JSON payload
        try:
            event = json.loads(payload.decode("utf-8"))
            data = event.get('data', {})
            event_type = event.get('event')
            #logging.info(event_type)
            #logging.info(data)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid JSON format")

        # Acknowledge receipt immediately by returning 200 OK
        background_tasks.add_task(crud.process_paystack_event, data, event_type, background_tasks)

        return {"status": "success"}

    except Exception as e:
        logging.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
