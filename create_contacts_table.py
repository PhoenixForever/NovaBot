
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            contact_name VARCHAR(100) NOT NULL,
            phone_number VARCHAR(20) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_contact_name (contact_name)
        )
    """)

    connection.commit()
    print("Contacts table created successfully!")

except mysql.connector.Error as error:
    print("Database setup failed:", error)

finally:
    if cursor is not None:
        cursor.close()
    if connection is not None and connection.is_connected():
        connection.close()
