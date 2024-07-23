import smtplib
from email.mime.text import MIMEText
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Form, UploadFile, File, Response, Depends
from datetime import datetime, date
import schemas
import crud
import uuid
from schemas import ItemRegistration
from crud import get_tag_by_tag1, update_tag, save_item_registration, update_user_items, upload_to_firebase
from fastapi import FastAPI, HTTPException, Path, Query

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
            # registered_items=0,
            # lost_items=0,
            # found_items=0,
            # items={}

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
        if not db_user:
            raise HTTPException(status_code=400, detail="Invalid email or password")
        return db_user
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
    print("tag aquired1")
    if not tag:
        print("tag aquired2")
        raise HTTPException(status_code=404, detail="Tag not found")

    if tag.is_owned:
        print("tag aquired3")
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
        print("tag aquired4")
        raise HTTPException(status_code=500, detail="Failed to save item registration")

    if not await update_user_items(uuid, item):
        print("tag aquired5")
        raise HTTPException(status_code=500, detail="Failed to update user's items")

    if not await update_tag(tag_id, uuid):
        print("tag aquired8")
        raise HTTPException(status_code=500, detail="Failed to update the tag")

    return {"message": "Item registered successfully"}


@app.post("/forgot-password/")
async def forgot_password(request: schemas.ForgotPasswordRequest):
    try:
        token = await crud.create_reset_token(request.email_address)
        if token:
            reset_link = f"https://lfreturnme.com/#/ForgotPasswordEmail/?token={token}"
            send_email(request.email_address, reset_link)
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


def send_email(to_email: str, reset_link: str):
    msg = MIMEText(f"Click the link to reset your password: {reset_link}")
    msg['Subject'] = 'Password Reset Request'
    msg['From'] = 'your-email@example.com'
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL('mail.lfreturnme.com', 465) as server:
            server.login("infonfo@lfreturnme.com", "lfreturnme@1")
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
    try:
        # Find user by UUID
        user = await crud.users_collection.find_one({"uuid": uuid})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if the item with the given tag_id exists in the user's items
        if tagid not in user.get("items", {}):
            raise HTTPException(status_code=404, detail=f"Item with tag ID {tagid} not found for user")

        # Update the item's status in the user's items
        user["items"][tagid]["status"] = str(new_status)

        # Update user document with the modified items dictionary
        user_result = await crud.users_collection.update_one(
            {"uuid": uuid},
            {"$set": {"items": user["items"]}}
        )

        if user_result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update item status in user's items")

        # Find item in the items collection by tag_id
        item = await crud.items_collection.find_one({"tag_id": tagid})
        if not item:
            raise HTTPException(status_code=404, detail="Item not found in items collection")

        # Update the item's status in the items collection
        item_result = await crud.items_collection.update_one(
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
