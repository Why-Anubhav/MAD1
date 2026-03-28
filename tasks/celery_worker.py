import os
import sys

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from celery import Celery
from celery.schedules import crontab

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

celery_app = Celery(
    "hms",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["tasks.scheduled_jobs"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    beat_schedule={
        # Daily appointment reminders at 8:00 AM
        "daily-appointment-reminders": {
            "task": "tasks.scheduled_jobs.send_daily_reminders",
            "schedule": crontab(hour=8, minute=0),
        },
        # Monthly doctor activity reports on 1st of each month at 6:00 AM
        "monthly-doctor-reports": {
            "task": "tasks.scheduled_jobs.send_monthly_doctor_report",
            "schedule": crontab(day_of_month=1, hour=6, minute=0),
        },
    },
)


def get_flask_app():
    """Lazy import to avoid circular dependencies."""
    from app import create_app
    return create_app("development")


# ─── User Triggered: CSV Export ───────────────────────────────────────────────

@celery_app.task(name="tasks.celery_worker.export_patient_csv_task", bind=True)
def export_patient_csv_task(self, patient_id: int, patient_email: str):
    """Export patient treatment history to CSV and notify via email."""
    flask_app = get_flask_app()
    with flask_app.app_context():
        from models import Patient
        from utils.csv_export import generate_patient_csv
        from utils.email_service import send_csv_ready_notification

        patient = Patient.query.get(patient_id)
        if not patient:
            return {"status": "error", "message": "Patient not found"}

        export_dir = flask_app.config.get(
            "EXPORT_DIR",
            os.path.join(os.path.dirname(__file__), "..", "exports")
        )

        filename = generate_patient_csv(patient, export_dir)
        download_url = f"http://localhost:5000/api/exports/{filename}"

        send_csv_ready_notification(
            patient_email=patient_email,
            patient_name=patient.user.username if patient.user else "Patient",
            download_url=download_url,
        )

        return {"status": "success", "filename": filename, "download_url": download_url}
