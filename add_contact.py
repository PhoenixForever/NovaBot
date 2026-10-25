
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

name = input("Enter contact name: ").strip()
phone = input("Enter WhatsApp number with country code: ").strip()

if not name or not phone:
    print("Name and phone number cannot be empty.")
    raise SystemExit(1)

connection = None
cursor = None

try:
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "24379")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        ssl_disabled=False,
        connection_timeout=15,
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO contacts (contact_name, phone_number)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE phone_number = %s
        """,
        (name, phone, phone),
    )

    connection.commit()
    print(f"Contact '{name}' saved successfully!")

except mysql.connector.Error as error:
    print("Could not save contact:", error)

finally:
    if cursor is not None:
        cursor.close()
    if connection is not None and connection.is_connected():
        connection.close()
