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