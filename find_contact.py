
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

name = input("Enter saved contact name: ").strip()

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
        SELECT contact_name, phone_number
        FROM contacts
        WHERE LOWER(contact_name) = LOWER(%s)
        """,
        (name,),
    )

    contact = cursor.fetchone()

    if contact:
        print(f"Contact found: {contact[0]}")
        print("Phone number is saved and ready to use.")
    else:
        print("Contact not found. Check the saved name.")

except mysql.connector.Error as error:
    print("Contact lookup failed:", error)

finally:
    if cursor is not None:
        cursor.close()
    if connection is not None and connection.is_connected():
        connection.close()
