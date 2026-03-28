from flask import Blueprint, request, jsonify
from extensions import db
from models import Doctor, Appointment, Treatment, Patient
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from datetime import datetime, date

doctor_bp = Blueprint("doctor", __name__)


def doctor_required(claims=None):
    if claims is None:
        claims = get_jwt()
    return claims.get("role") == "doctor"


def get_doctor_profile():
    claims = get_jwt()
    user_id = int(get_jwt_identity())
    return Doctor.query.filter_by(user_id=user_id).first()


# ─── Appointments ─────────────────────────────────────────────────────────────

@doctor_bp.route("/appointments", methods=["GET"])
@jwt_required()
def get_appointments():
    if not doctor_required():
        return jsonify({"error": "Doctor access required"}), 403

    doctor = get_doctor_profile()
    if not doctor:
        return jsonify({"error": "Doctor profile not found"}), 404

    filter_type = request.args.get("filter", "upcoming")  # today / upcoming / all
    today_str = date.today().isoformat()

    query = Appointment.query.filter_by(doctor_id=doctor.id)

    if filter_type == "today":
        query = query.filter_by(date=today_str)
    elif filter_type == "upcoming":
        query = query.filter(
            Appointment.date >= today_str,
            Appointment.status == "booked"
        )
    # "all" returns everything

    appointments = query.order_by(Appointment.date.asc(), Appointment.time.asc()).all()
    return jsonify([a.to_dict() for a in appointments]), 200


@doctor_bp.route("/appointments/<int:appt_id>/status", methods=["PUT"])
@jwt_required()
def update_appointment_status(appt_id):
    if not doctor_required():
        return jsonify({"error": "Doctor access required"}), 403

    doctor = get_doctor_profile()
    appt = Appointment.query.get_or_404(appt_id)

    if appt.doctor_id != doctor.id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    new_status = data.get("status")

    valid_transitions = {
        "booked": ["completed", "cancelled"],
        "completed": [],
        "cancelled": [],
    }

    if new_status not in valid_transitions.get(appt.status, []):
        return jsonify({"error": f"Cannot transition from '{appt.status}' to '{new_status}'"}), 400

    appt.status = new_status
    db.session.commit()
    return jsonify({"message": f"Appointment marked as {new_status}", "appointment": appt.to_dict()}), 200


# ─── Treatment ────────────────────────────────────────────────────────────────

@doctor_bp.route("/treatment", methods=["POST"])
@jwt_required()
def add_treatment():
    if not doctor_required():
        return jsonify({"error": "Doctor access required"}), 403

    doctor = get_doctor_profile()
    data = request.get_json()
    appt_id = data.get("appointment_id")
    if not appt_id:
        return jsonify({"error": "appointment_id is required"}), 400

    appt = Appointment.query.get_or_404(appt_id)
    if appt.doctor_id != doctor.id:
        return jsonify({"error": "Unauthorized"}), 403

    if appt.treatment:
        # Update existing
        appt.treatment.diagnosis = data.get("diagnosis", appt.treatment.diagnosis)
        appt.treatment.prescription = data.get("prescription", appt.treatment.prescription)
        appt.treatment.notes = data.get("notes", appt.treatment.notes)
    else:
        treatment = Treatment(
            appointment_id=appt_id,
            diagnosis=data.get("diagnosis", ""),
            prescription=data.get("prescription", ""),
            notes=data.get("notes", ""),
        )
        db.session.add(treatment)

        # Auto-complete appointment
        if appt.status == "booked":
            appt.status = "completed"

    db.session.commit()
    return jsonify({"message": "Treatment saved", "treatment": appt.treatment.to_dict()}), 200


@doctor_bp.route("/treatment/<int:appt_id>", methods=["GET"])
@jwt_required()
def get_treatment(appt_id):
    if not doctor_required():
        return jsonify({"error": "Doctor access required"}), 403

    appt = Appointment.query.get_or_404(appt_id)
    if not appt.treatment:
        return jsonify({"diagnosis": "", "prescription": "", "notes": ""}), 200
    return jsonify(appt.treatment.to_dict()), 200


# ─── Patients ─────────────────────────────────────────────────────────────────

@doctor_bp.route("/patients", methods=["GET"])
@jwt_required()
def get_patients():
    if not doctor_required():
        return jsonify({"error": "Doctor access required"}), 403

    doctor = get_doctor_profile()
    if not doctor:
        return jsonify({"error": "Doctor profile not found"}), 404

    # Get unique patients from appointments
    appts = Appointment.query.filter_by(doctor_id=doctor.id).all()
    seen = set()
    patients = []
    for a in appts:
        if a.patient_id not in seen:
            seen.add(a.patient_id)
            patients.append(a.patient.to_dict())

    return jsonify(patients), 200


@doctor_bp.route("/patients/<int:patient_id>/history", methods=["GET"])
@jwt_required()
def get_patient_history(patient_id):
    if not doctor_required():
        return jsonify({"error": "Doctor access required"}), 403

    patient = Patient.query.get_or_404(patient_id)
    treatments = []
    for appt in patient.appointments:
        if appt.treatment:
            treatments.append(appt.treatment.to_dict())

    return jsonify({"patient": patient.to_dict(), "treatments": treatments}), 200


# ─── Availability ─────────────────────────────────────────────────────────────

@doctor_bp.route("/availability", methods=["POST"])
@jwt_required()
def set_availability():
    if not doctor_required():
        return jsonify({"error": "Doctor access required"}), 403

    doctor = get_doctor_profile()
    if not doctor:
        return jsonify({"error": "Doctor profile not found"}), 404

    data = request.get_json()
    # Expect: {"availability": {"2025-07-01": ["09:00","10:00"], ...}}
    new_availability = data.get("availability", {})
    if not isinstance(new_availability, dict):
        return jsonify({"error": "availability must be a JSON object {date: [slots]}"}), 400

    doctor.availability = new_availability
    db.session.commit()
    return jsonify({"message": "Availability updated", "availability": doctor.availability}), 200


@doctor_bp.route("/availability", methods=["GET"])
@jwt_required()
def get_availability():
    if not doctor_required():
        return jsonify({"error": "Doctor access required"}), 403

    doctor = get_doctor_profile()
    if not doctor:
        return jsonify({"error": "Doctor profile not found"}), 404

    return jsonify({"availability": doctor.availability or {}}), 200


# ─── Dashboard Summary ────────────────────────────────────────────────────────

@doctor_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    if not doctor_required():
        return jsonify({"error": "Doctor access required"}), 403

    doctor = get_doctor_profile()
    if not doctor:
        return jsonify({"error": "Doctor profile not found"}), 404

    today_str = date.today().isoformat()

    today_appts = Appointment.query.filter_by(doctor_id=doctor.id, date=today_str).count()
    upcoming_appts = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.date >= today_str,
        Appointment.status == "booked"
    ).count()
    total_patients = len(set(
        a.patient_id for a in Appointment.query.filter_by(doctor_id=doctor.id).all()
    ))

    return jsonify({
        "today_appointments": today_appts,
        "upcoming_appointments": upcoming_appts,
        "total_patients": total_patients,
        "doctor": doctor.to_dict(),
    }), 200
