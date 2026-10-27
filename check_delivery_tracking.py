
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
    ssl_disabled=False,
    connection_timeout=15,
)

cursor = connection.cursor(dictionary=True)

for table in (
    "whatsapp_status_events",
    "scheduled_message_deliveries",
):
    print(f"\n--- {table} ---")
    cursor.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()

    if rows:
        for row in rows:
            print(row)
    else:
        print("No records found.")

cursor.close()
connection.close()
