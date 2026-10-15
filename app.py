from email.mime import message

from flask import Flask, request
from dotenv import load_dotenv
import os

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

import requests
import json

from groq import Groq

import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.DEBUG)

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

def send_reminder(phone_number, reminder_text):
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

    data = request.get_json()

    try:
        messages = data["entry"][0]["changes"][0]["value"].get("messages", [])

        for message in messages:
            message_id = message.get("id")

            if not message_id:
                continue

            if message_id in processed_message_ids:
                print("Duplicate message ignored:", message_id)
                continue

            if message.get("type") == "text":
                processed_message_ids.add(message_id)
                user_message = message["text"]["body"]

                print("Message received from WhatsApp:")
                print(user_message)
                
                
            if is_reminder_request(user_message):
                print("Reminder request detected!")

                reminder_time = extract_reminder_time(user_message)
                print("Extracted reminder time:", reminder_time)

                
                if reminder_time:
                    sender = message.get("from")

                    if sender:
                        scheduler.add_job(
                            send_reminder,
                            "date",
                            run_date=reminder_time,
                            args=[sender, user_message]
                        )
                        
                        print("Scheduled jobs:", scheduler.get_jobs(), flush=True)
                        print("Scheduler running:", scheduler.running, flush=True)
                        print("Server time:", datetime.now(), flush=True)

                        for job in scheduler.get_jobs():
                            print("Job ID:", job.id, flush=True)
                            print("Next run time:", job.next_run_time, flush=True)

                        print("Scheduler timezone:", scheduler.timezone, flush=True)


                        reply_text = "✅ NovaBot has scheduled your reminder!"
                        print("Confirmation message:", reply_text)
                    else:
                        reply_text = "Sorry, I couldn't identify your WhatsApp number."

                else:
                    reply_text = "Please specify the time, for example: Remind me to study DSA in 2 minutes."
            else:
                reply_text = get_ai_response(user_message)


                sender = message.get("from")

                if sender:
                    send_whatsapp_message(sender, reply_text)
                    print("Confirmation send function completed.")

                

    except (KeyError, IndexError, TypeError):
        print("No message found in this webhook event.")

    return "EVENT_RECEIVED", 200



if not scheduler.running:
    scheduler.start()
    print("NovaBot reminder scheduler is running!")

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)