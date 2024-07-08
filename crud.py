# import mysql.connector
# from mysql.connector import Error
# import schemas
# import uuid
# import bcrypt
#
#
# def check_credentials(email_address, connection):
#     query = f"""
#                 SELECT COUNT(*)
#                 FROM users
#                 WHERE
#                 email_address = '{email_address}'
#                     """
#     #OR uuid = '{uuid}'
#     cursor1 = connection.cursor()
#     cursor1.execute(query)
#     rows = cursor1.fetchone()
#
#     count = rows[0]  #[row.count for row in rows]
#     #print(count)
#     if count > 0:
#
#         return False
#     else:
#         return True
#
#
# def create_user(user: schemas.Signup):
#     try:
#         connection = mysql.connector.connect(
#             host="localhost",
#             user="root",
#             passwd="Halifas2001",
#             database="lfreturnme"
#         )
#         user_uuid = str(uuid.uuid4())  # Generate a unique UUID
#         hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
#         cursor = connection.cursor()
#         if connection.is_connected():
#
#             chck = check_credentials(user.email_address, connection)
#             print(chck)
#             if chck:
#                 print(connection.is_connected())
#
#                 print(cursor)
#                 insert_query = """INSERT INTO users (uuid, full_name, email_address, date_of_birth, address, id_no, profile_picture, phone_number, gender, valid_id_type, id_card_image, password)
#                                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
#                 cursor.execute(insert_query, (
#                     user_uuid, user.full_name, user.email_address, user.date_of_birth, user.address, user.id_no,
#                     user.profile_picture, user.phone_number, user.gender, user.valid_id_type, user.id_card_image,
#                     hashed_password.decode('utf-8')
#                 ))
#                 connection.commit()
#                 user.uuid = user_uuid  # Assign the generated UUID to the user object
#                 return user
#             else:
#                 print("Sorry, use another information! Credentials seem to exist")
#                 return None
#         #print("hello1")
#
#     except Error as e:
#         print(f"Error: {e}")
#         #print("hello2")
#     finally:
#         if connection.is_connected():
#             cursor.close()
#             connection.close()
#             return None
#
#     #print("hello3")
#
#
# def authenticate_user(email_address: str, password: str):
#     try:
#         connection = mysql.connector.connect(
#             host="localhost",
#             user="root",
#             passwd="Halifas2001",
#             database="lfreturnme"
#         )
#         if connection.is_connected():
#             cursor = connection.cursor(dictionary=True)
#             select_query = "SELECT * FROM users WHERE email_address = %s"
#             cursor.execute(select_query, (email_address,))
#             user = cursor.fetchone()
#             if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
#                 return user
#     except Error as e:
#         print(f"Error: {e}")
#     finally:
#         if connection.is_connected():
#             cursor.close()
#             connection.close()
#     return None

#
# import mysql.connector
# from mysql.connector import Error
# import schemas
# import uuid
# import bcrypt
#
#
# def check_credentials(email_address, connection):
#     try:
#         query = """
#             SELECT COUNT(*)
#             FROM users
#             WHERE email_address = %s
#         """
#         cursor = connection.cursor()
#         cursor.execute(query, (email_address,))
#         rows = cursor.fetchone()
#         count = rows[0]
#         print(f"check_credentials: email_address={email_address}, count={count}")  # Debugging information
#         return count == 0
#     except Error as e:
#         print(f"Error in check_credentials: {e}")
#         return False
#
#
# def create_user(user: schemas.Signup):
#     connection = None
#     cursor = None
#     try:
#         connection = mysql.connector.connect(
#             host="sql8.freesqldatabase.com",
#             user="sql8717709",
#             passwd="rWjn79V1mX",
#             database="sql8717709"
#         )
#         user_uuid = str(uuid.uuid4())  # Generate a unique UUID
#         hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
#         cursor = connection.cursor()
#         if connection.is_connected():
#             if check_credentials(user.email_address, connection):
#                 insert_query = """
#                     INSERT INTO users (
#                         uuid, full_name, email_address, date_of_birth, address, id_no, profile_picture,
#                         phone_number, gender, valid_id_type, id_card_image, password
#                     ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#                 """
#                 cursor.execute(insert_query, (
#                     user_uuid, user.full_name, user.email_address, user.date_of_birth, user.address, user.id_no,
#                     user.profile_picture, user.phone_number, user.gender, user.valid_id_type, user.id_card_image,
#                     hashed_password.decode('utf-8')
#                 ))
#                 connection.commit()
#                 user.uuid = user_uuid  # Assign the generated UUID to the user object
#                 return user
#             else:
#                 print("create_user: Email address already exists")  # Debugging information
#                 return None
#     except Error as e:
#         print(f"Error in create_user: {e}")
#         return None
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()
#
#
# def authenticate_user(email_address: str, password: str):
#     connection = None
#     cursor = None
#     try:
#         connection = mysql.connector.connect(
#             host="sql8.freesqldatabase.com",
#             user="sql8717709",
#             passwd="rWjn79V1mX",
#             database="sql8717709"
#         )
#         if connection.is_connected():
#             cursor = connection.cursor(dictionary=True)
#             select_query = "SELECT * FROM users WHERE email_address = %s"
#             cursor.execute(select_query, (email_address,))
#             user = cursor.fetchone()
#             if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
#                 return user
#     except Error as e:
#         print(f"Error in authenticate_user: {e}")
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()
#     return None
import motor.motor_asyncio
import schemas
import uuid
import bcrypt
import logging

logger = logging.getLogger(__name__)

# MongoDB connection setup
client = motor.motor_asyncio.AsyncIOMotorClient("mongodb+srv://Admin:AITeKaIUZtKdYbvu@lfreturnme.vjjpets.mongodb.net/?retryWrites=true&w=majority&appName=LFReturnMe")
database = client["LFReturnMe"]
users_collection = database["users"]

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
        user_uuid = str(uuid.uuid4())  # Generate a unique UUID
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

        if await check_credentials(user.email_address):
            user_data = {
                "uuid": user_uuid,
                "full_name": user.full_name,
                "email_address": user.email_address,
                "date_of_birth": user.date_of_birth.isoformat(),  # Save as string
                "address": user.address,
                "id_no": user.id_no,
                "profile_picture": user.profile_picture,
                "phone_number": user.phone_number,
                "gender": user.gender,
                "valid_id_type": user.valid_id_type,
                "id_card_image": user.id_card_image,
                "password": hashed_password.decode('utf-8')
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
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            logger.info("User authenticated successfully: %s", email_address)
            return schemas.ResponseSignup(**user)
        else:
            logger.warning("Authentication failed for user: %s", email_address)
            return None
    except Exception as e:
        logger.error("Error in authenticate_user: %s", e)
        raise
