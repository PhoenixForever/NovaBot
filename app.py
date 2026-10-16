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

def extract_reminder_time(user_message):
    match = re.search(
        r"in (\d+) minutes?",
        user_message.lower()
    )

    if match:
        minutes = int(match.group(1))
        return datetime.now() + timedelta(minutes=minutes)

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
                    try:
                        job = scheduler.add_job(
                            send_reminder,
                            trigger="date",
                            run_date=reminder_time,
                            args=[sender, user_message],
                            misfire_grace_time=300
                        )

                        print("Reminder job ID:", job.id, flush=True)
                        print("Reminder next run:", job.next_run_time, flush=True)
                        print("Scheduler thread alive after adding job:", scheduler._thread.is_alive() if scheduler._thread else None, flush=True)
                        print("Scheduler running:", scheduler.running, flush=True)
                        print("Scheduler thread alive:", scheduler._thread.is_alive(), flush=True)
                        print("Scheduler state:", scheduler.state, flush=True)
                        print("Scheduler paused:", scheduler.state == 2, flush=True)

                        reply_text = (
                            "✅ NovaBot has scheduled your reminder!"
                        )

                    except Exception as e:
                        print("Scheduling error:", repr(e), flush=True)
                        reply_text = (
                            "Sorry, I couldn't schedule that reminder."
                        )
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

if not scheduler.running or not scheduler._thread.is_alive():
    print("Starting or restarting scheduler...", flush=True)
    scheduler.start()
    print(
        "Scheduler started. Thread alive:",
        scheduler._thread.is_alive(),
        flush=True
    )

print("Scheduler running:", scheduler.running, flush=True)
print("Scheduler state:", scheduler.state, flush=True)
print(
    "Scheduler thread alive:",
    scheduler._thread.is_alive() if scheduler._thread else False,
    flush=True
)

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
