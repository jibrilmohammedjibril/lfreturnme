import mysql.connector
from mysql.connector import Error
import schemas
import uuid
import bcrypt


def create_user(user: schemas.Signup):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="Halifas2001",
            database="lfreturnme"
        )
        if connection.is_connected():
            cursor = connection.cursor()
            user_uuid = str(uuid.uuid4())  # Generate a unique UUID
            hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
            insert_query = """INSERT INTO users (uuid, full_name, email_address, date_of_birth, address, id_no, profile_picture, phone_number, gender, valid_id_type, id_card_image, password)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(insert_query, (
                user_uuid, user.full_name, user.email_address, user.date_of_birth, user.address, user.id_no,
                user.profile_picture, user.phone_number, user.gender, user.valid_id_type, user.id_card_image,
                hashed_password.decode('utf-8')
            ))
            connection.commit()
            user.uuid = user_uuid  # Assign the generated UUID to the user object
            return user
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def authenticate_user(email_address: str, password: str):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="Halifas2001",
            database="lfreturnme"
        )
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            select_query = "SELECT * FROM users WHERE email_address = %s"
            cursor.execute(select_query, (email_address,))
            user = cursor.fetchone()
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                return user
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return None
