from pydantic import BaseModel, Field, EmailStr
from datetime import date, datetime
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
    subscription_status: Optional[str] = None
    tier: Optional[str] = None
    subscription_code: Optional[str] = None
    subscription_end: Optional[str] = None


class Signup(BaseModel):
    uuid: Optional[str] = None
    full_name: str
    email_address: EmailStr
    date_of_birth: date
    address: str
    profile_picture: str
    phone_number: str
    gender: str
    password: str
    is_verified: bool


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
    #id_no: Optional[str] = None
    profile_picture: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[str] = None
    #valid_id_type: Optional[str] = None
    #id_card_image: Optional[str] = None
    password: Optional[str] = None
    is_verified: Optional[bool] = None
    access_token: Optional[str] = None
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


class NewsletterEmail(BaseModel):
    email: EmailStr


class LostFound(BaseModel):
    item: str
    name: str
    location: str
    date: str
    tag_id: Optional[str] = None
    phone_number: str
    email: EmailStr
    description: str
    item_image: str


class UpdateProfileRequest(BaseModel):
    profile_picture: str


# Model to receive email data
class OTPRequest(BaseModel):
    email: EmailStr


class OTPVerify(BaseModel):
    email: EmailStr
    otp: int


class SubscriptionUpdate(BaseModel):
    subscription_code: str = Field(..., description="The subscription code to update")
    subscription_status: str = Field(..., description="The status of the subscription")
    tier: Optional[str] = Field(None, description="Subscription tier (optional for inactive subscriptions)")
    subscription_end: Optional[str] = Field(None, description="Date for subscription expiration")


class PaystackWebhookPayload(BaseModel):
    event: str
    data: dict
