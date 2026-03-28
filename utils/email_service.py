from flask_mail import Message
from extensions import mail


def send_email(to: str, subject: str, html_body: str, text_body: str = ""):
    """
    Send an email using Flask-Mail.
    Falls back gracefully if mail is not configured.
    """
    try:
        msg = Message(
            subject=subject,
            recipients=[to],
            html=html_body,
            body=text_body or _strip_tags(html_body),
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[Email] Failed to send to {to}: {e}")
        return False


def send_appointment_reminder(patient_email: str, patient_name: str, doctor_name: str, date: str, time: str):
    subject = "🏥 Appointment Reminder — Today"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
        <h2 style="color: #2c7be5;">Appointment Reminder</h2>
        <p>Dear <strong>{patient_name}</strong>,</p>
        <p>This is a reminder that you have an appointment today:</p>
        <table style="border-collapse: collapse; width: 100%;">
            <tr><td style="padding: 8px; font-weight: bold;">Doctor:</td><td style="padding: 8px;">{doctor_name}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">Date:</td><td style="padding: 8px;">{date}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">Time:</td><td style="padding: 8px;">{time}</td></tr>
        </table>
        <p>Please arrive 15 minutes early. <br>— HMS Team</p>
    </div>
    """
    return send_email(patient_email, subject, html)


def send_monthly_doctor_report(doctor_email: str, doctor_name: str, report_html: str):
    subject = f"📊 Monthly Activity Report — {doctor_name}"
    return send_email(doctor_email, subject, report_html)


def send_csv_ready_notification(patient_email: str, patient_name: str, download_url: str):
    subject = "✅ Your Treatment History Export is Ready"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
        <h2 style="color: #2c7be5;">Export Ready</h2>
        <p>Dear <strong>{patient_name}</strong>,</p>
        <p>Your treatment history CSV export is ready for download:</p>
        <p><a href="{download_url}" style="background: #2c7be5; color: white; padding: 10px 20px;
            border-radius: 4px; text-decoration: none;">Download CSV</a></p>
        <p>The file will be available for 24 hours. <br>— HMS Team</p>
    </div>
    """
    return send_email(patient_email, subject, html)


def _strip_tags(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html)
