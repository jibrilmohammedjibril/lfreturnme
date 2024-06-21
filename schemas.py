from pydantic import BaseModel
from datetime import date
from typing import Optional  # Import Optional for uuid


class Signup(BaseModel):
    uuid: Optional[str] = None  # Add uuid field
    full_name: str
    email_address: str
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
    email_address: str
    password: str


class TagRegistration(BaseModel):
    item_name: str
    item_image: str
    item_serial_number: str
    purchase_date: date
    proof_of_purchase: str
    tag_number: int
