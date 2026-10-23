from email.mime import message

from flask import Flask, request
from dotenv import load_dotenv
import os

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

import requests
import json
import apscheduler

from groq import Groq

import logging

import mysql.connector
import secrets

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True
)

logging.getLogger("apscheduler").setLevel(logging.DEBUG)
logging.getLogger("apscheduler.scheduler").setLevel(logging.DEBUG)
logging.getLogger("apscheduler.executors").setLevel(logging.DEBUG)


load_dotenv()

app = Flask(__name__)

def is_reminder_request(user_message):
    return user_message.lower().startswith("remind me")

import re


from datetime import datetime, timedelta, timezone

def extract_reminder_time(user_message):
    match = re.search(
        r"in (\d+) minutes?",
        user_message.lower()
    )

    if match:
        minutes = int(match.group(1))
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)

    return None


scheduler = BackgroundScheduler(timezone="UTC")
def scheduler_event_listener(event):
    print(
        "SCHEDULER EVENT:",
        type(event).__name__,
        getattr(event, "exception", None),
        flush=True
    )

scheduler.add_listener(scheduler_event_listener)
print("APScheduler version:", apscheduler.__version__, flush=True)

def send_reminder(phone_number, reminder_text):
    print("Scheduler thread alive:", scheduler._thread.is_alive(), flush=True)
    print("🚨 REMINDER FUNCTION STARTED!", flush=True)
    print("Sending reminder to:", phone_number, flush=True)
    print("Reminder:", reminder_text, flush=True)

    send_whatsapp_message(
        phone_number,
        "🔔 NovaBot Reminder: " + reminder_text
    )


processed_message_ids = set()


groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_ai_response(user_message):
    try:
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        print("AI error:", e)
        return "Sorry, I'm having trouble answering right now. Please try again."


VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")


WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")


def send_whatsapp_message(to, message_text):
    message_text = message_text[:4000]
    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": message_text
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    print("WhatsApp API status:", response.status_code)
    print("WhatsApp API response:", response.text)

    return response


@app.route("/")
def home():
    return "NovaBot is running!"


@app.route("/webhook", methods=["GET"])
def verify_webhook():

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403



@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json(silent=True) or {}

    try:
        messages = (
            data["entry"][0]["changes"][0]["value"]
            .get("messages", [])
        )

        for message in messages:
            message_id = message.get("id")

            if not message_id:
                continue

            if message_id in processed_message_ids:
                print("Duplicate message ignored:", message_id, flush=True)
                continue

            # Process text messages only
            if message.get("type") != "text":
                continue

            processed_message_ids.add(message_id)

            user_message = message["text"]["body"]
            sender = message.get("from")

            print("Message received from WhatsApp:", flush=True)
            print(user_message, flush=True)

            if not sender:
                print("Sender number not found.", flush=True)
                continue

            # Handle reminder requests
            if is_reminder_request(user_message):
                print("Reminder request detected!", flush=True)

                reminder_time = extract_reminder_time(user_message)
                print("Extracted reminder time:", reminder_time, flush=True)

               
                if reminder_time:
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
                            INSERT INTO reminders
                                (phone_number, reminder_text, scheduled_at, status)
                            VALUES (%s, %s, %s, 'pending')
                            """,
                            (
                                sender,
                                user_message,
                                reminder_time.replace(tzinfo=None),
                            ),
                        )

                        connection.commit()

                        print(
                            "Reminder saved to MySQL. ID:",
                            cursor.lastrowid,
                            flush=True,
                        )

                        reply_text = "✅ NovaBot has saved your reminder!"

                    except Exception as e:
                        print("Database scheduling error:", repr(e), flush=True)
                        reply_text = "Sorry, I couldn't save that reminder."

                    finally:
                        if cursor is not None:
                            cursor.close()
                        if connection is not None and connection.is_connected():
                            connection.close()

                else:
                    reply_text = (
                        "Please specify the time, for example: "
                        "Remind me to study DSA in 2 minutes."
                    )

            # Handle ordinary AI questions
            else:
                reply_text = get_ai_response(user_message)

            # Send exactly one response for this incoming message
            try:
                response = send_whatsapp_message(sender, reply_text)
                print(
                    "Reply HTTP status:",
                    response.status_code,
                    flush=True
                )
            except Exception as e:
                print("WhatsApp reply error:", repr(e), flush=True)

    except (KeyError, IndexError, TypeError) as e:
        print("Webhook payload error:", repr(e), flush=True)

    return "EVENT_RECEIVED", 200



print("Scheduler object:", scheduler, flush=True)

if not scheduler.running:
    scheduler.start()

print("Scheduler running:", scheduler.running, flush=True)
print(
    "Scheduler thread alive:",
    scheduler._thread.is_alive() if scheduler._thread else False,
    flush=True
)

@app.route("/internal/cron-health", methods=["GET"])
def cron_health_endpoint():
    expected_secret = os.getenv("REMINDER_CRON_SECRET")
    provided_secret = request.headers.get("X-Cron-Secret", "")

    if not expected_secret or not secrets.compare_digest(
        provided_secret, expected_secret
    ):
        return {"error": "Unauthorized"}, 401

    return {"success": True, "message": "Cron authentication works"}, 200

@app.route("/internal/process-reminders", methods=["POST"])
def process_reminders_endpoint():
    # Protect this endpoint with our secret key.
    expected_secret = os.getenv("REMINDER_CRON_SECRET")
    provided_secret = request.headers.get("X-Cron-Secret", "")

    if not expected_secret or not secrets.compare_digest(
        provided_secret, expected_secret
    ):
        return {"error": "Unauthorized"}, 401

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

        sent = 0
        failed = 0

        for reminder in reminders:
            try:
                response = send_whatsapp_message(
                    reminder["phone_number"],
                    "🔔 NovaBot Reminder: "
                    + reminder["reminder_text"],
                )
                response.raise_for_status()

                new_status = "sent"
                sent += 1

            except Exception:
                logging.exception(
                    "Reminder delivery failed: %s",
                    reminder["id"],
                )
                new_status = "failed"
                failed += 1

            update_connection = None
            update_cursor = None

            try:
                update_connection = mysql.connector.connect(
                    host=os.getenv("DB_HOST"),
                    port=int(os.getenv("DB_PORT", "24379")),
                    database=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    ssl_disabled=False,
                    connection_timeout=15,
                )

                update_cursor = update_connection.cursor()
                update_cursor.execute(
                    "UPDATE reminders SET status = %s WHERE id = %s",
                    (new_status, reminder["id"]),
                )
                update_connection.commit()

            finally:
                if update_cursor is not None:
                    update_cursor.close()
                if (
                    update_connection is not None
                    and update_connection.is_connected()
                ):
                    update_connection.close()

        return {
            "success": True,
            "checked": len(reminders),
            "sent": sent,
            "failed": failed,
        }, 200

    except Exception:
        if connection is not None and connection.is_connected():
            connection.rollback()

        logging.exception("Reminder endpoint failed")
        return {"error": "Reminder processing failed"}, 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)