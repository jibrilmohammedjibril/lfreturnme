# from pydantic import BaseModel, Field, EmailStr
# from datetime import date, datetime
# from typing import Optional, List, Dict  # Import Optional for uuid
# from bson import ObjectId
# from pydantic.networks import EmailStr
#
#
# class PyObjectId(ObjectId):
#     @classmethod
#     def __get_validators__(cls):
#         yield cls.validate
#
#     @classmethod
#     def validate(cls, v):
#         if not ObjectId.is_valid(v):
#             raise ValueError('Invalid ObjectId')
#         return ObjectId(v)
#
#     @classmethod
#     def __modify_schema__(cls, field_schema):
#         field_schema.update(type='string')
#
#     @classmethod
#     def __get_pydantic_json_schema__(cls, schema, handler):
#         return schema
#
#
# class ItemRegistration(BaseModel):
#     item_id: str
#     item_type: str
#     item_name: str
#     tag_id: str
#     item_image: Optional[str]
#     item_description: str
#     uuid: str
#     registered_date: Optional[str] = None
#     status: Optional[str] = None
#
#
# # Signup model
# class Signup(BaseModel):
#     uuid: Optional[str] = None  # Add uuid field
#     full_name: str
#     email_address: str
#     date_of_birth: date
#     address: str
#     id_no: str
#     profile_picture: str
#     phone_number: str
#     gender: str
#     valid_id_type: str
#     id_card_image: str
#     password: str
#     # registered_items: Optional[int] = 0
#     # lost_items: Optional[int] = 0
#     # found_items: Optional[int] = 0
#     # items: Dict[str, ItemRegistration] = {}
#     # registered_items: Optional[int] = 0
#     # lost_items: Optional[int] = 0
#     # found_items: Optional[int] = 0
#
#
# # ResponseSignup model
#
#
# # Signin model
# class Signin(BaseModel):
#     email_address: str
#     password: str
#
#
# # TagRegistration model
# class TagRegistration(BaseModel):
#     item_name: str
#     item_image: str
#     item_serial_number: str
#     purchase_date: date
#     proof_of_purchase: str
#     tag_number: int
#
#
# class ItemRegistration(BaseModel):
#     item_id: str
#     item_type: str
#     item_name: str
#     tag_id: str
#     item_image: Optional[str]
#     item_description: str
#     uuid: str
#     registered_date: Optional[str] = None
#     status: Optional[str] = None
#
#
# class ResponseSignup(BaseModel):
#     uuid: Optional[str] = None  # Add uuid field
#     full_name: Optional[str] = None
#     email_address: Optional[str] = None
#     date_of_birth: Optional[date] = None
#     address: Optional[str] = None
#     id_no: Optional[str] = None
#     profile_picture: Optional[str] = None
#     phone_number: Optional[str] = None
#     gender: Optional[str] = None
#     valid_id_type: Optional[str] = None
#     id_card_image: Optional[str] = None
#     password: Optional[str] = None
#     registered_items: Optional[int] = 0
#     lost_items: Optional[int] = 0
#     found_items: Optional[int] = 0
#     items: Dict[str, ItemRegistration] = {}
#
#
#
# class User(BaseModel):
#     id: Optional[PyObjectId] = None
#     uuid: str
#     full_name: str
#     email_address: str
#     date_of_birth: str
#     address: str
#     id_no: str
#     profile_picture: str
#     phone_number: str
#     gender: str
#     valid_id_type: str
#     id_card_image: str
#     password: str
#
#
# class Tag(BaseModel):
#     id: int
#     tag1: str
#     date: str
#     tagid: str
#     status: str
#     tag_name: str
#     uuid: str
#     is_owned: bool = False
#
#     class Config:
#         arbitrary_types_allowed = True
#         json_encoders = {
#             ObjectId: str
#         }
#
#
# # Dashboard model (placeholder)
#
# class Dashboard(BaseModel):
#     id: Optional[PyObjectId] = Field(alias="_id")
#     uuid: str
#     full_name: str
#     email_address: EmailStr
#     date_of_birth: str
#     address: str
#     id_no: str
#     profile_picture: str
#     phone_number: str
#     gender: str
#     valid_id_type: str
#     id_card_image: str
#     password: str
#
#     # items: Dict[str, ItemRegistration] = {}
#     # registered_items: Optional[int] = 0
#     # lost_items: Optional[int] = 0
#     # found_items: Optional[int] = 0
#
#     class Config:
#         arbitrary_types_allowed = True
#         json_encoders = {ObjectId: str}
#
#
# class ForgotPasswordRequest(BaseModel):
#     email_address: EmailStr
#
#
# class ResetPasswordRequest(BaseModel):
#     token: str
#     new_password: str


from pydantic import BaseModel, Field, EmailStr
from datetime import date
from typing import Optional, Dict
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError('Invalid ObjectId')
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type='string')


class ItemRegistration(BaseModel):
    item_id: str
    item_type: str
    item_name: str
    tag_id: str
    item_image: Optional[str]
    item_description: str
    uuid: str
    registered_date: Optional[str] = None
    status: Optional[str] = None


class Signup(BaseModel):
    uuid: Optional[str] = None
    full_name: str
    email_address: EmailStr
    date_of_birth: date
    address: str
    id_no: str
    profile_picture: str
    phone_number: str
    gender: str
    valid_id_type: str
    id_card_image: str
    password: str


class Signin(BaseModel):
    email_address: EmailStr
    password: str


class Tag(BaseModel):
    id: int
    tag1: str
    date: str
    tagid: str
    tag_name: str
    uuid: str
    is_owned: bool

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ResponseSignup(BaseModel):
    uuid: Optional[str] = None
    full_name: Optional[str] = None
    email_address: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    id_no: Optional[str] = None
    profile_picture: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[str] = None
    valid_id_type: Optional[str] = None
    id_card_image: Optional[str] = None
    password: Optional[str] = None
    registered_items: Optional[int] = 0
    lost_items: Optional[int] = 0
    found_items: Optional[int] = 0
    items: Dict[str, ItemRegistration] = {}


class Dashboard(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    uuid: str
    full_name: str
    email_address: EmailStr
    date_of_birth: str
    address: str
    id_no: str
    profile_picture: str
    phone_number: str
    gender: str
    valid_id_type: str
    id_card_image: str
    password: str

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ForgotPasswordRequest(BaseModel):
    email_address: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class UpdateStatusRequest(BaseModel):
    status: str
