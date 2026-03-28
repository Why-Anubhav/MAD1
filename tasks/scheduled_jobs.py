"""
Scheduled Celery jobs:
1. send_daily_reminders   — every morning at 8 AM
2. send_monthly_doctor_report — 1st of month at 6 AM
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from tasks.celery_worker import celery_app
from datetime import date


@celery_app.task(name="tasks.scheduled_jobs.send_daily_reminders")
def send_daily_reminders():
    """Check today's appointments and send reminder emails to patients."""
    from app import create_app
    flask_app = create_app("development")

    with flask_app.app_context():
        from models import Appointment
        from utils.email_service import send_appointment_reminder

        today = date.today().isoformat()
        appointments = Appointment.query.filter_by(date=today, status="booked").all()

        sent = 0
        for appt in appointments:
            try:
                patient = appt.patient
                doctor = appt.doctor
                if patient and patient.user and doctor and doctor.user:
                    success = send_appointment_reminder(
                        patient_email=patient.user.email,
                        patient_name=patient.user.username,
                        doctor_name=doctor.user.username,
                        date=appt.date,
                        time=appt.time,
                    )
                    if success:
                        sent += 1
            except Exception as e:
                print(f"[Reminder] Error for appointment {appt.id}: {e}")

        print(f"[Daily Reminders] Sent {sent}/{len(appointments)} reminders for {today}")
        return {"date": today, "total": len(appointments), "sent": sent}


@celery_app.task(name="tasks.scheduled_jobs.send_monthly_doctor_report")
def send_monthly_doctor_report():
    """Generate and email HTML activity reports to all doctors for the previous month."""
    from app import create_app
    flask_app = create_app("development")

    with flask_app.app_context():
        from models import Doctor, Appointment, Treatment
        from utils.email_service import send_monthly_doctor_report as send_report
        from datetime import datetime
        import calendar

        today = datetime.utcnow()
        # report for previous month
        if today.month == 1:
            report_month = 12
            report_year = today.year - 1
        else:
            report_month = today.month - 1
            report_year = today.year

        month_name = calendar.month_name[report_month]
        month_prefix = f"{report_year}-{report_month:02d}"

        doctors = Doctor.query.all()
        reports_sent = 0

        for doctor in doctors:
            if not doctor.user or not doctor.user.is_active:
                continue

            appts = Appointment.query.filter(
                Appointment.doctor_id == doctor.id,
                Appointment.date.like(f"{month_prefix}%"),
            ).all()

            total = len(appts)
            completed = sum(1 for a in appts if a.status == "completed")
            cancelled = sum(1 for a in appts if a.status == "cancelled")

            diagnoses = []
            prescriptions = []
            for a in appts:
                if a.treatment:
                    if a.treatment.diagnosis:
                        diagnoses.append(a.treatment.diagnosis)
                    if a.treatment.prescription:
                        prescriptions.append(a.treatment.prescription)

            report_html = _build_doctor_report_html(
                doctor_name=doctor.user.username,
                month_name=month_name,
                year=report_year,
                total=total,
                completed=completed,
                cancelled=cancelled,
                diagnoses=diagnoses,
                prescriptions=prescriptions,
            )

            success = send_report(
                doctor_email=doctor.user.email,
                doctor_name=doctor.user.username,
                report_html=report_html,
            )
            if success:
                reports_sent += 1

        print(f"[Monthly Report] Sent {reports_sent}/{len(doctors)} reports for {month_name} {report_year}")
        return {"month": f"{month_name} {report_year}", "sent": reports_sent}


def _build_doctor_report_html(doctor_name, month_name, year, total, completed, cancelled, diagnoses, prescriptions):
    diag_list = "".join(f"<li>{d}</li>" for d in diagnoses[:10]) or "<li>No diagnoses recorded</li>"
    presc_list = "".join(f"<li>{p}</li>" for p in prescriptions[:10]) or "<li>No prescriptions recorded</li>"

    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 700px; color: #333;">
        <h2 style="color: #2c7be5;">Monthly Activity Report — {month_name} {year}</h2>
        <p>Dear Dr. <strong>{doctor_name}</strong>,</p>
        <p>Here is your activity summary for <strong>{month_name} {year}</strong>:</p>

        <h3>📊 Appointment Summary</h3>
        <table style="border-collapse: collapse; width: 100%;">
            <tr style="background: #f0f4ff;">
                <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Metric</th>
                <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Count</th>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd;">Total Appointments</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{total}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd;">Completed</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{completed}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd;">Cancelled</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{cancelled}</td>
            </tr>
        </table>

        <h3>🔬 Diagnoses Given (last 10)</h3>
        <ul>{diag_list}</ul>

        <h3>💊 Prescriptions Issued (last 10)</h3>
        <ul>{presc_list}</ul>

        <p style="color: #888; font-size: 12px;">This is an automated report generated by HMS.</p>
    </div>
    """
