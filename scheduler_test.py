
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta

scheduler = BlockingScheduler()

def my_reminder(message):
    print("🔔 NovaBot Reminder:", message)
    print("Time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

reminder_time = datetime.now() + timedelta(seconds=30)

scheduler.add_job(
    my_reminder,
    "date",
    run_date=reminder_time,
    args=["Take a break and drink some water!"]
)

print("Reminder scheduled for:", reminder_time.strftime("%H:%M:%S"))
scheduler.start()
