
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
        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            sender_phone VARCHAR(30) NOT NULL,
            recipient_phone VARCHAR(30) NOT NULL,
            message_text TEXT NOT NULL,
            scheduled_at DATETIME NOT NULL,
            status ENUM(
                'pending',
                'processing',
                'sent',
                'failed',
                'cancelled'
            ) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_at DATETIME NULL,
            INDEX idx_scheduled_due (status, scheduled_at)
        )
    """)

    connection.commit()
    print("SUCCESS: scheduled_messages table is ready!")

except Exception as error:
    print("Database setup failed:", repr(error))

finally:
    if cursor is not None:
        cursor.close()

    if connection is not None and connection.is_connected():
        connection.close()
