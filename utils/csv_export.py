import csv
import os
from datetime import datetime


def generate_patient_csv(patient, export_dir: str) -> str:
    """
    Generate a CSV file of a patient's treatment history.
    Returns the file path.
    """
    os.makedirs(export_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"patient_{patient.id}_history_{timestamp}.csv"
    filepath = os.path.join(export_dir, filename)

    fieldnames = [
        "user_id",
        "username",
        "doctor",
        "department",
        "appointment_date",
        "appointment_time",
        "appointment_status",
        "diagnosis",
        "prescription",
        "notes",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for appt in patient.appointments:
            treatment = appt.treatment
            writer.writerow({
                "user_id": patient.user_id,
                "username": patient.user.username if patient.user else "",
                "doctor": appt.doctor.user.username if appt.doctor and appt.doctor.user else "",
                "department": appt.doctor.department.name if appt.doctor and appt.doctor.department else "",
                "appointment_date": appt.date,
                "appointment_time": appt.time,
                "appointment_status": appt.status,
                "diagnosis": treatment.diagnosis if treatment else "",
                "prescription": treatment.prescription if treatment else "",
                "notes": treatment.notes if treatment else "",
            })

    return filename
