
import os
import time
import logging
import requests
import mysql.connector
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "24379")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        ssl_disabled=False,
        connection_timeout=15,
    )


def send_whatsapp_message(to, message_text):
    phone_number_id = os.getenv("PHONE_NUMBER_ID")
    whatsapp_token = os.getenv("WHATSAPP_TOKEN")

    if not phone_number_id or not whatsapp_token:
        raise RuntimeError("WhatsApp environment variables are missing")

    url = (
        "https://graph.facebook.com/v26.0/"
        f"{phone_number_id}/messages"
    )

    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message_text[:4000]},
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response


def check_reminders():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        cursor.execute("""
            SELECT id, phone_number, reminder_text
            FROM reminders
            WHERE status = 'pending'
              AND scheduled_at <= %s
            ORDER BY scheduled_at ASC
            LIMIT 20
            FOR UPDATE
        """, (now,))

        reminders = cursor.fetchall()

        for reminder in reminders:
            cursor.execute("""
                UPDATE reminders
                SET status = 'processing'
                WHERE id = %s AND status = 'pending'
            """, (reminder["id"],))

        connection.commit()

        for reminder in reminders:
            reminder_id = reminder["id"]

            try:
                response = send_whatsapp_message(
                    reminder["phone_number"],
                    "🔔 NovaBot Reminder: "
                    + reminder["reminder_text"],
                )

                logging.info(
                    "WhatsApp accepted reminder %s (HTTP %s)",
                    reminder_id,
                    response.status_code,
                )

                new_status = "sent"

            except Exception:
                logging.exception(
                    "Delivery failed for reminder %s",
                    reminder_id,
                )
                new_status = "failed"

            update_connection = None
            update_cursor = None

            try:
                update_connection = get_connection()
                update_cursor = update_connection.cursor()

                update_cursor.execute("""
                    UPDATE reminders
                    SET status = %s
                    WHERE id = %s AND status = 'processing'
                """, (new_status, reminder_id))

                update_connection.commit()

            finally:
                if update_cursor is not None:
                    update_cursor.close()
                if (
                    update_connection is not None
                    and update_connection.is_connected()
                ):
                    update_connection.close()

    except Exception:
        if connection is not None and connection.is_connected():
            connection.rollback()
        logging.exception("Error checking reminders")

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


def check_scheduled_messages():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        cursor.execute(
            """
            SELECT id, recipient_phone, message_text
            FROM scheduled_messages
            WHERE status = 'pending'
              AND scheduled_at <= %s
            ORDER BY scheduled_at ASC
            LIMIT 20
            FOR UPDATE
            """,
            (now,),
        )

        messages = cursor.fetchall()

        for item in messages:
            cursor.execute(
                """
                UPDATE scheduled_messages
                SET status = 'processing'
                WHERE id = %s AND status = 'pending'
                """,
                (item["id"],),
            )

        connection.commit()

        for item in messages:
            message_id = item["id"]
            update_connection = None
            update_cursor = None

            try:
                send_whatsapp_message(
                    item["recipient_phone"],
                    item["message_text"],
                )
                new_status = "sent"
                logging.info(
                    "Scheduled message %s sent successfully",
                    message_id,
                )

            except Exception:
                new_status = "failed"
                logging.exception(
                    "Failed to send scheduled message %s",
                    message_id,
                )

            finally:
                try:
                    update_connection = get_connection()
                    update_cursor = update_connection.cursor()
                    update_cursor.execute(
                        """
                        UPDATE scheduled_messages
                        SET status = %s,
                            sent_at = CASE
                                WHEN %s = 'sent' THEN UTC_TIMESTAMP()
                                ELSE sent_at
                            END
                        WHERE id = %s
                        """,
                        (new_status, new_status, message_id),
                    )
                    update_connection.commit()
                except Exception:
                    logging.exception(
                        "Could not update scheduled message %s status",
                        message_id,
                    )
                finally:
                    if update_cursor is not None:
                        update_cursor.close()
                    if (
                        update_connection is not None
                        and update_connection.is_connected()
                    ):
                        update_connection.close()

    except Exception:
        if connection is not None and connection.is_connected():
            connection.rollback()
        logging.exception("Error checking scheduled messages")

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

if __name__ == "__main__":
    logging.info("NovaBot reminder worker started")

    while True:
        check_reminders()
        time.sleep(10)
