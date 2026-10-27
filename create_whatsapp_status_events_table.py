
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    ssl_ca=os.getenv("DB_SSL_CA") or None,
)

cursor = connection.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS whatsapp_status_events (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        whatsapp_message_id VARCHAR(255) NOT NULL,
        delivery_status VARCHAR(20) NOT NULL,
        error_details TEXT NULL,
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_whatsapp_message_id (whatsapp_message_id)
    )
""")

connection.commit()

cursor.close()
connection.close()

print("SUCCESS! The WhatsApp status events table is ready.")
