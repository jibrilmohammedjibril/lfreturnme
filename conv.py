
import pymysql
import pymongo

# MySQL connection details


mysql_connection = pymysql.connect(
    host="localhost",
    user="root",
    passwd="Halifas2001",
    database="lfreturnme"
)

# MongoDB connection details
mongo_client = pymongo.MongoClient("mongodb+srv://Admin:AITeKaIUZtKdYbvu@lfreturnme.vjjpets.mongodb.net/?retryWrites=true&w=majority&appName=LFReturnMe")
mongo_db = mongo_client["LFReturnMe"]
mongo_collection = mongo_db["tags"]

# Fetch data from MySQL
with mysql_connection.cursor() as cursor:
    cursor.execute("SELECT * FROM tags")
    rows = cursor.fetchall()

# Convert MySQL data to MongoDB format and insert
documents = []
for row in rows:
    document = {
        "id": row[0],
        "tag1": row[1],
        "date": row[2],
        "tagid": row[3],
        "status": row[4],
        "tag_name": row[5],
        "email": row[6]
    }
    documents.append(document)

mongo_collection.insert_many(documents)

print("Data transferred successfully!")
