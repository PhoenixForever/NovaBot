
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import time

def test_reminder():
    print("SUCCESS! Reminder executed at:", datetime.now(), flush=True)

scheduler = BackgroundScheduler()
scheduler.add_job(
    test_reminder,
    trigger="date",
    run_date=datetime.now() + timedelta(seconds=15)
)

scheduler.start()
print("Scheduler started at:", datetime.now(), flush=True)
print("Waiting 15 seconds for the reminder...", flush=True)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    scheduler.shutdown()
    print("Scheduler stopped.", flush=True)
