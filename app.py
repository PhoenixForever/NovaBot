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

import fitz
import io
from zoneinfo import ZoneInfo
import base64

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


def transcribe_voice_note(audio_bytes, filename="voice.ogg"):
    """Convert a WhatsApp voice note into text using Groq."""

    try:
        transcription = groq_client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3-turbo",
            response_format="text"
        )

        return str(transcription).strip()

    except Exception as e:
        print("Voice transcription error:", repr(e), flush=True)
        raise


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

#WhatsApp media download function
def download_whatsapp_media(media_id):
    """Download a media file from WhatsApp using its media ID."""

    # Step 1: Ask WhatsApp for the media download URL
    url = f"https://graph.facebook.com/v26.0/{media_id}"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20
    )
    response.raise_for_status()

    media_url = response.json().get("url")

    if not media_url:
        raise ValueError("WhatsApp did not return a media URL.")

    # Step 2: Download the actual file
    media_response = requests.get(
        media_url,
        headers=headers,
        timeout=60
    )
    media_response.raise_for_status()

    return media_response.content, media_response.headers.get(
        "Content-Type", "application/octet-stream"
    )

#text extraction from PDF function
def extract_pdf_text(file_bytes):
    """Extract readable text from a PDF stored in memory."""

    with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
        if len(pdf) == 0:
            raise ValueError("The PDF has no pages.")

        text_parts = []

        for page in pdf:
            page_text = page.get_text()
            if page_text.strip():
                text_parts.append(page_text)

    extracted_text = "\n\n".join(text_parts).strip()

    if not extracted_text:
        raise ValueError(
            "No readable text found. The PDF may contain scanned pages."
        )

    return extracted_text

#PDF summarization function
def summarize_pdf_text(pdf_text):
    """Generate a concise summary of extracted PDF text."""

    prompt = f"""
You are NovaBot, a helpful AI assistant.

Summarize the following PDF in clear, simple language.

Include:
1. The main topic and purpose
2. The most important points
3. Important facts, dates, or figures
4. Key conclusions
5. Action items, if any

Use headings and bullet points.
Do not invent information that is not in the document.

PDF TEXT:
{pdf_text[:12000]}
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=1200
    )

    return response.choices[0].message.content.strip()

#Image analysis function
def analyze_image(image_bytes, content_type, question="Describe this image in detail."):
    """Analyze an image using Groq's vision model."""

    if content_type not in ("image/jpeg", "image/png", "image/webp","image/jpg"):
        raise ValueError("Unsupported image format.")

    if len(image_bytes) > 20 * 1024 * 1024:
        raise ValueError("The image exceeds the 20 MB limit.")

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    response = groq_client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": question
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        temperature=0.3,
        max_tokens=1000
    )

    return response.choices[0].message.content.strip()


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

def parse_scheduled_message(user_message):
    pattern = (
        r"schedule a message to (.+?) at "
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) "
        r"saying (.+)"
    )

    match = re.match(pattern, user_message.strip(), re.IGNORECASE)

    if not match:
        return None

    contact_name = match.group(1).strip()
    time_text = match.group(2).strip()
    message_text = match.group(3).strip()

    try:
        scheduled_local = datetime.strptime(
            time_text, "%Y-%m-%d %H:%M"
        ).replace(tzinfo=ZoneInfo("Asia/Kolkata"))

        scheduled_utc = scheduled_local.astimezone(
            ZoneInfo("UTC")
        ).replace(tzinfo=None)

        if scheduled_local <= datetime.now(ZoneInfo("Asia/Kolkata")):
            return None

    except ValueError:
        return None

    return contact_name, scheduled_utc, message_text


def find_contact_by_name(contact_name):
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
            (contact_name.strip(),),
        )

        return cursor.fetchone()

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

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

            
            # Identify supported incoming message types
            message_type = message.get("type")

            if message_type not in ("text", "image", "document", "audio"):
                print("Unsupported message type:", message_type, flush=True)
                continue

            processed_message_ids.add(message_id)
            sender = message.get("from")

            if not sender:
                print("Sender number not found.", flush=True)
                continue

            
            if message_type == "text":
                user_message = message["text"]["body"]

            
            elif message_type == "image":
                user_message = ""


            elif message_type == "document":
                user_message = ""

            elif message_type == "audio":
                user_message = ""

          
            # Handle reminder requests only for text messages
            if message_type == "text" and is_reminder_request(user_message):
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

            
            # Handle scheduled WhatsApp messages
            elif message_type == "text" and user_message.lower().startswith(
                "schedule a message to "
            ):
                parsed = parse_scheduled_message(user_message)

                if not parsed:
                    reply_text = (
                        "Please use this format:\n"
                        "Schedule a message to Rahul at 2026-10-26 09:00 "
                        "saying Good morning."
                    )
                else:
                    contact_name, scheduled_at, message_text = parsed

                    try:
                        contact = find_contact_by_name(contact_name)

                        if not contact:
                            reply_text = (
                                f"I couldn't find '{contact_name}' in your saved "
                                "contacts. Add the contact first and try again."
                            )
                        else:
                            recipient_name, recipient_phone = contact

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
                            try:
                                cursor.execute(
                                    """
                                    INSERT INTO scheduled_messages
                                        (sender_phone, recipient_phone, message_text,
                                        scheduled_at, status)
                                    VALUES (%s, %s, %s, %s, 'pending')
                                    """,
                                    (
                                        sender,
                                        recipient_phone,
                                        message_text,
                                        scheduled_at,
                                    ),
                                )
                                connection.commit()
                            finally:
                                cursor.close()
                                connection.close()

                            reply_text = (
                                f"✅ Message scheduled for {recipient_name} "
                                f"at {scheduled_at.strftime('%Y-%m-%d %H:%M')} UTC.\n"
                                f"Message: {message_text}"
                            )

                    except Exception as e:
                        print("Scheduled message error:", repr(e), flush=True)
                        reply_text = (
                            "Sorry, I couldn't schedule that message. "
                            "Please try again."
                        )

            # Handle ordinary AI questions
            elif message_type == "text":
                reply_text = get_ai_response(user_message)


            
            # Voice note understanding & response
            elif message_type == "audio":
                audio = message.get("audio", {})
                media_id = audio.get("id")
                mime_type = audio.get("mime_type", "audio/ogg")
                extension = "ogg"

                if "mpeg" in mime_type:
                    extension = "mp3"
                elif "mp4" in mime_type:
                    extension = "m4a"
                elif "wav" in mime_type:
                    extension = "wav"

                try:
                    if not media_id:
                        raise ValueError("Audio media ID is missing.")

                    audio_bytes, content_type = download_whatsapp_media(media_id)

                    if not audio_bytes:
                        raise ValueError("Downloaded audio file is empty.")

                    transcript = transcribe_voice_note(
                        audio_bytes,
                        filename=f"voice.{extension}"
                    )

                    if not transcript:
                        reply_text = "Sorry, I couldn't understand that voice note. Please try again."
                    else:
                        reply_text = get_ai_response(transcript)

                except Exception as e:
                    print("Voice note processing error:", repr(e), flush=True)
                    reply_text = (
                        "Sorry, I couldn't process that voice note. "
                        "Please try sending it again."
                    )

            #Image understanding & response
            elif message_type == "image":
                image = message.get("image", {})
                image_question = image.get("caption", "").strip()
                media_id = image.get("id")

                try:
                    if not media_id:
                        raise ValueError("Image media ID is missing.")

                    file_bytes, content_type = download_whatsapp_media(media_id)

                    # Use the actual downloaded content type when available.
                    if content_type:
                        content_type = content_type.split(";")[0].strip().lower()

                    if content_type not in (
                        "image/jpeg",
                        "image/png",
                        "image/webp",
                        "image/jpg"
                    ):
                        content_type = (
                            image.get("mime_type", "")
                            .split(";")[0]
                            .strip()
                            .lower()
                        )

                    # Normalize JPG to the standard JPEG MIME type
                    if content_type == "image/jpg":
                        content_type = "image/jpeg"

                    if not image_question:
                        image_question = "Describe this image and identify its important details."

                    answer = analyze_image(
                        file_bytes,
                        content_type,
                        question=image_question
                    )

                    reply_text = "🖼️ *Image Analysis*\n\n" + answer

                except Exception as e:
                    print("Image analysis error:", repr(e), flush=True)
                    reply_text = (
                        "Sorry, I couldn't analyze this image. "
                        "Please try sending a JPEG, PNG, JPG or WebP image."
                    )


            #PDF understanding & response
            elif message_type == "document":
                document = message.get("document", {})
                filename = document.get("filename", "unknown.pdf")
                mime_type = document.get("mime_type", "")

                if not (
                    filename.lower().endswith(".pdf")
                    or mime_type == "application/pdf"
                ):
                    reply_text = "📄 Please send a PDF file so I can summarize it."

                else:
                    media_id = document.get("id")

                    try:
                        if not media_id:
                            raise ValueError("PDF media ID is missing.")

                        
                        file_bytes, content_type = download_whatsapp_media(media_id)

                        if not file_bytes.startswith(b"%PDF-"):
                            raise ValueError("The downloaded file is not a valid PDF.")

                        if len(file_bytes) > 10 * 1024 * 1024:
                            raise ValueError(
                                "The PDF is larger than NovaBot's 10 MB processing limit."
                            )

                        pdf_text = extract_pdf_text(file_bytes)
                        reply_text = summarize_pdf_text(pdf_text)

                        reply_text = "📄 *PDF Summary*\n\n" + reply_text

                    except Exception as e:
                        print("PDF summarization error:", repr(e), flush=True)
                        reply_text = (
                            "Sorry, I couldn't summarize this PDF. "
                            "Please check that it contains readable text and try again."
                        )


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
    logging.error("DIAGNOSTIC: process_reminders_endpoint entered")
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

        
            try:
                logging.info("DEBUG: Reached scheduled-message processing")
                scheduled_result = process_due_scheduled_messages()
            except Exception as e:
                logging.exception("Scheduled message call failed")
                scheduled_result = {"error": str(e)}

            return {
                "success": True,
                "checked": len(reminders),
                "sent": sent,
                "failed": failed,
                "scheduled_messages": scheduled_result,
            }, 200


    except Exception as e:
        if connection is not None and connection.is_connected():
            connection.rollback()

        logging.exception("Reminder endpoint failed: %s", e)
        return {"error": str(e)}, 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()
    return {"error": "Reminder endpoint reached an unexpected exit"}, 500

def process_due_scheduled_messages():
    connection = None
    cursor = None
    sent = 0
    failed = 0

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
            new_status = "failed"
            update_connection = None
            update_cursor = None

            try:
                response = send_whatsapp_message(
                    item["recipient_phone"],
                    item["message_text"],
                )
                response.raise_for_status()
                new_status = "sent"
                sent += 1

            except Exception:
                failed += 1
                logging.exception(
                    "Scheduled message delivery failed: %s",
                    message_id,
                )

            finally:
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
                        "Could not update scheduled message status: %s",
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

        return {"checked": len(messages), "sent": sent, "failed": failed}

    except Exception:
        if connection is not None and connection.is_connected():
            connection.rollback()
        logging.exception("Scheduled-message processing failed")
        return {"checked": 0, "sent": sent, "failed": failed}

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

@app.route("/debug-routes", methods=["GET"])
def debug_routes():
    return {
        "app_file": os.path.abspath(__file__),
        "routes": sorted(
            str(rule) for rule in app.url_map.iter_rules()
        )
    }, 200

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)