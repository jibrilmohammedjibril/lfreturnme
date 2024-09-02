# import mysql.connector
#
# db = mysql.connector.connect(
#     host="localhost",
#     user="root",
#     passwd="Halifas2001",
#     database ="lfreturnme"
#     )
#
# mycursor = db.cursor()
#
# #mycursor.execute("CREATE DATABASE lfreturnme")
#
# #mycursor.execute("CREATE TABLE tags(id int(11) NOT NULL,tag1 varchar(300) NOT NULL,date varchar(300) NOT NULL,tagid varchar(300) NOT NULL,status varchar(30) NOT NULL,tag_name varchar(300) NOT NULL,email varchar(300) NOT NULL)")
# #mycursor.execute("CREATE TABLE users(id int(11) NOT NULL,tag1 varchar(300) NOT NULL,date varchar(300) NOT NULL,tagid varchar(300) NOT NULL,status varchar(30) NOT NULL,tag_name varchar(300) NOT NULL,email varchar(300) NOT NULL)")
# mycursor.execute("SELECT * FROM tags LIMIT 1;")
#
# for x in mycursor:
#     print(x[2]


from pymongo import MongoClient

# Replace the connection string with your MongoDB connection string
client = MongoClient(
    "mongodb+srv://Admin:AITeKaIUZtKdYbvu@lfreturnme.vjjpets.mongodb.net/?retryWrites=true&w=majority&appName=LFReturnMe")
db = client["LFReturnMe"]
collection = db["tags"]

# Define the update operation
update_operation = {
        "$set": {
            "subscription_status": "inactive"
        }
}


# Apply the update operation to all documents
result = collection.update_many({}, update_operation)

# Print the result
print(f"Matched {result.matched_count} documents and modified {result.modified_count} documents.")
