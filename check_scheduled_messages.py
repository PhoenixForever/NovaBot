import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "24379")),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    ssl_disabled=False
)

cursor = connection.cursor(dictionary=True)

cursor.execute("""
    SELECT id, recipient_phone, message_text,
           scheduled_at, status, sent_at
    FROM scheduled_messages
    ORDER BY id DESC
    LIMIT 5
""")

for row in cursor.fetchall():
    print(row)

cursor.close()
connection.close()