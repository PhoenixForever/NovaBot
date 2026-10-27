
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
        CREATE TABLE IF NOT EXISTS scheduled_message_deliveries (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            scheduled_message_id BIGINT NOT NULL,
            whatsapp_message_id VARCHAR(255) NOT NULL UNIQUE,
            delivery_status VARCHAR(20) NOT NULL DEFAULT 'accepted',
            error_details TEXT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_scheduled_message_id (scheduled_message_id),
            INDEX idx_delivery_status (delivery_status)
        )
    """)

    connection.commit()
    print("SUCCESS: delivery tracking table is ready!")

except Exception as error:
    print("Database setup failed:", repr(error))

finally:
    if cursor is not None:
        cursor.close()

    if connection is not None and connection.is_connected():
        connection.close()
