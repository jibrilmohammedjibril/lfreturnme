# from fastapi import FastAPI, HTTPException
# import schemas
# import crud
#
# app = FastAPI()
#
#
# @app.post("/signup/", response_model=schemas.ResponseSignup)
# def signup(user: schemas.Signup):
#     try:
#         db_user = crud.create_user(user=user)
#         if db_user:
#             return db_user
#         else:
#             raise HTTPException(status_code=400, detail="Email address already exists")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# @app.get("/signin/")  #response_model=schemas.Signin)
# def signin(email_address: str, password: str):
#     try:
#         db_user = crud.authenticate_user(email_address, password)
#         print(db_user)
#         if not db_user:
#             #print("invalid email or password")
#             raise HTTPException(status_code=400, detail="Invalid email or password")
#         return db_user
#     except Exception as e:
#         raise HTTPException(status_code=400, detail="Invalid email or password2")
#         #raise HTTPException(status_code=500, detail="Internal server error")


# from fastapi import FastAPI, HTTPException, File, UploadFile, Form
# import schemas
# import crud
# import aiofiles
# import os
# from datetime import datetime
#
# app = FastAPI()
#
#
# @app.post("/signup/", response_model=schemas.ResponseSignup)
# async def signup(
#         full_name: str = Form(...),
#         email_address: str = Form(...),
#         date_of_birth: str = Form(...),
#         address: str = Form(...),
#         id_no: str = Form(...),
#         phone_number: str = Form(...),
#         gender: str = Form(...),
#         valid_id_type: str = Form(...),
#         id_card_image: str = Form(...),
#         password: str = Form(...),
#         profile_picture: UploadFile = File(...)
# ):
#     try:
#         # Parse date_of_birth from string to date object
#         date_of_birth_obj = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
#
#         # Save the profile picture to a directory
#         profile_picture_dir = "profile_pictures"
#         os.makedirs(profile_picture_dir, exist_ok=True)
#         profile_picture_path = os.path.join(profile_picture_dir, profile_picture.filename)
#
#         async with aiofiles.open(profile_picture_path, 'wb') as out_file:
#             content = await profile_picture.read()
#             await out_file.write(content)
#
#         # Create a user object
#         user = schemas.Signup(
#             full_name=full_name,
#             email_address=email_address,
#             date_of_birth=date_of_birth_obj,  # Use the parsed date object
#             address=address,
#             id_no=id_no,
#             phone_number=phone_number,
#             gender=gender,
#             valid_id_type=valid_id_type,
#             id_card_image=id_card_image,
#             password=password,
#             profile_picture=profile_picture_path
#         )
#
#         db_user = crud.create_user(user=user)
#         if db_user:
#             return db_user
#         #else:
#             #raise HTTPException(status_code=400, detail="Email address already exists")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# @app.get("/signin/")  # response_model=schemas.Signin)
# def signin(user: schemas.Signin):
#     try:
#         db_user = crud.authenticate_user(user.email_address, user.password)
#         if not db_user:
#             raise HTTPException(status_code=400, detail="Invalid email or password")
#         return db_user
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Internal server error")
#
# from fastapi.middleware.cors import CORSMiddleware
#
# from fastapi import FastAPI, HTTPException, Form, UploadFile, File
# from datetime import datetime
# import os
# import aiofiles
# import schemas
# import crud
#
# app = FastAPI()
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Adjust this to the specific origins you want to allow
#     allow_credentials=True,
#     allow_methods=["*"],  # Allow all methods
#     allow_headers=["*"],  # Allow all headers
# )
#
# @app.post("/signup/", response_model=schemas.ResponseSignup)
# async def signup(
#         full_name: str = Form(...),
#         email_address: str = Form(...),
#         date_of_birth: str = Form(...),
#         address: str = Form(...),
#         id_no: str = Form(...),
#         phone_number: str = Form(...),
#         gender: str = Form(...),
#         valid_id_type: str = Form(...),
#         password: str = Form(...),
#         profile_picture: UploadFile = File(...),
#         id_card_image: UploadFile = File(...)
# ):
#     try:
#         # Parse date_of_birth from string to date object
#         date_of_birth_obj = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
#
#         # Save the profile picture to a directory
#         profile_picture_dir = "profile_pictures"
#         os.makedirs(profile_picture_dir, exist_ok=True)
#         profile_picture_path = os.path.join(profile_picture_dir, profile_picture.filename)
#
#         async with aiofiles.open(profile_picture_path, 'wb') as out_file:
#             content = await profile_picture.read()
#             await out_file.write(content)
#
#         # Save the ID card image to a directory
#         id_card_image_dir = "id_card_images"
#         os.makedirs(id_card_image_dir, exist_ok=True)
#         id_card_image_path = os.path.join(id_card_image_dir, id_card_image.filename)
#
#         async with aiofiles.open(id_card_image_path, 'wb') as out_file:
#             content = await id_card_image.read()
#             await out_file.write(content)
#
#         # Create a user object
#         user = schemas.Signup(
#             full_name=full_name,
#             email_address=email_address,
#             date_of_birth=date_of_birth_obj,
#             address=address,
#             id_no=id_no,
#             phone_number=phone_number,
#             gender=gender,
#             valid_id_type=valid_id_type,
#             id_card_image=id_card_image_path,
#             password=password,
#             profile_picture=profile_picture_path
#         )
#
#         db_user = crud.create_user(user=user)
#         if db_user:
#             return db_user
#         else:
#             raise HTTPException(status_code=400, detail="Email address already exists")
#     except ValueError as ve:
#         print(f"ValueError: {ve}")  # Debugging information
#         raise HTTPException(status_code=400, detail=f"Invalid date format: {ve}")
#     except Exception as e:
#         print(f"Exception: {e}")  # Debugging information
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# @app.post("/signin/", response_model=schemas.ResponseSignup)
# def signin(user: schemas.Signin):
#     try:
#         db_user = crud.authenticate_user(user.email_address, user.password)
#         if not db_user:
#             raise HTTPException(status_code=400, detail="Invalid email or password")
#         return db_user
#     except Exception as e:
#         print(f"Exception: {e}")  # Debugging information
#         raise HTTPException(status_code=500, detail="Internal server error")
#
# #
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Form, UploadFile, File, Response
from datetime import datetime
import schemas
import crud
from mongodb_utils import upload_file_to_gridfs, get_file_from_gridfs

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to the specific origins you want to allow
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


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
        # Parse date_of_birth from string to date object
        date_of_birth_obj = datetime.strptime(date_of_birth, "%Y-%m-%d").date()

        # Read and upload profile picture to GridFS
        profile_picture_data = await profile_picture.read()
        profile_picture_id = await upload_file_to_gridfs(profile_picture_data, profile_picture.filename)

        # Read and upload ID card image to GridFS
        id_card_image_data = await id_card_image.read()
        id_card_image_id = await upload_file_to_gridfs(id_card_image_data, id_card_image.filename)

        # Create a user object
        user = schemas.Signup(
            full_name=full_name,
            email_address=email_address,
            date_of_birth=date_of_birth_obj,
            address=address,
            id_no=id_no,
            phone_number=phone_number,
            gender=gender,
            valid_id_type=valid_id_type,
            profile_picture=profile_picture_id,
            id_card_image=id_card_image_id,
            password=password
        )

        db_user = await crud.create_user(user=user)
        if db_user:
            return db_user
        else:
            raise HTTPException(status_code=400, detail="Email address already exists")
    except ValueError as ve:
        print(f"ValueError: {ve}")  # Debugging information
        raise HTTPException(status_code=400, detail=f"Invalid date format: {ve}")
    except Exception as e:
        print(f"Exception: {e}")  # Debugging information
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/signin/", response_model=schemas.ResponseSignup)
async def signin(user: schemas.Signin):
    try:
        db_user = await crud.authenticate_user(user.email_address, user.password)
        if not db_user:
            raise HTTPException(status_code=400, detail="Invalid email or password")
        return db_user
    except Exception as e:
        print(f"Exception: {e}")  # Debugging information
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/image/{file_id}")
async def get_image(file_id: str):
    try:
        file_data = await get_file_from_gridfs(file_id)
        return Response(content=file_data, media_type="image/jpeg")  # Adjust media_type based on your file type
    except Exception as e:
        print(f"Exception: {e}")  # Debugging information
        raise HTTPException(status_code=500, detail="Internal server error")
