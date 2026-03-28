from flask import Blueprint, request, jsonify
from extensions import db
from models import Appointment, Doctor, Patient
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from datetime import datetime, date

appointment_bp = Blueprint("appointment", __name__)


def get_patient_profile():
    user_id = int(get_jwt_identity())
    return Patient.query.filter_by(user_id=user_id).first()


# ─── Book Appointment ─────────────────────────────────────────────────────────

@appointment_bp.route("/book", methods=["POST"])
@jwt_required()
def book_appointment():
    claims = get_jwt()
    if claims.get("role") != "patient":
        return jsonify({"error": "Patient access required"}), 403

    patient = get_patient_profile()
    if not patient:
        return jsonify({"error": "Patient profile not found"}), 404

    data = request.get_json()
    required = ["doctor_id", "date", "time"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"{f} is required"}), 400

    doctor = Doctor.query.get(data["doctor_id"])
    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404

    if not doctor.user.is_active:
        return jsonify({"error": "Doctor is not available"}), 400

    # Check if slot is in doctor's availability
    avail = doctor.availability or {}
    date_str = data["date"]
    time_str = data["time"]

    if date_str in avail and time_str not in avail[date_str]:
        return jsonify({"error": "Selected time slot is not available"}), 400

    # Prevent double booking
    conflict = Appointment.query.filter_by(
        doctor_id=data["doctor_id"],
        date=date_str,
        time=time_str,
        status="booked"
    ).first()
    if conflict:
        return jsonify({"error": "This time slot is already booked"}), 409

    # Check patient doesn't already have appointment at same time
    patient_conflict = Appointment.query.filter_by(
        patient_id=patient.id,
        date=date_str,
        time=time_str,
        status="booked"
    ).first()
    if patient_conflict:
        return jsonify({"error": "You already have an appointment at this time"}), 409

    appt = Appointment(
        patient_id=patient.id,
        doctor_id=data["doctor_id"],
        date=date_str,
        time=time_str,
        status="booked",
        created_at=datetime.utcnow(),
    )
    db.session.add(appt)
    db.session.commit()
    return jsonify({"message": "Appointment booked successfully", "appointment": appt.to_dict()}), 201


# ─── List Patient Appointments ────────────────────────────────────────────────

@appointment_bp.route("/my", methods=["GET"])
@jwt_required()
def my_appointments():
    claims = get_jwt()
    if claims.get("role") != "patient":
        return jsonify({"error": "Patient access required"}), 403

    patient = get_patient_profile()
    if not patient:
        return jsonify({"error": "Patient profile not found"}), 404

    status = request.args.get("status")
    query = Appointment.query.filter_by(patient_id=patient.id)
    if status:
        query = query.filter_by(status=status)

    appointments = query.order_by(Appointment.date.desc(), Appointment.time.desc()).all()
    return jsonify([a.to_dict() for a in appointments]), 200


# ─── Reschedule Appointment ───────────────────────────────────────────────────

@appointment_bp.route("/<int:appt_id>/reschedule", methods=["PUT"])
@jwt_required()
def reschedule_appointment(appt_id):
    claims = get_jwt()
    if claims.get("role") != "patient":
        return jsonify({"error": "Patient access required"}), 403

    patient = get_patient_profile()
    appt = Appointment.query.get_or_404(appt_id)

    if appt.patient_id != patient.id:
        return jsonify({"error": "Unauthorized"}), 403

    if appt.status != "booked":
        return jsonify({"error": "Only booked appointments can be rescheduled"}), 400

    data = request.get_json()
    new_date = data.get("date")
    new_time = data.get("time")

    if not new_date or not new_time:
        return jsonify({"error": "date and time are required"}), 400

    # Check availability & conflicts
    doctor = appt.doctor
    avail = doctor.availability or {}
    if new_date in avail and new_time not in avail[new_date]:
        return jsonify({"error": "Selected time slot is not available"}), 400

    conflict = Appointment.query.filter_by(
        doctor_id=appt.doctor_id,
        date=new_date,
        time=new_time,
        status="booked"
    ).filter(Appointment.id != appt_id).first()
    if conflict:
        return jsonify({"error": "This time slot is already booked"}), 409

    appt.date = new_date
    appt.time = new_time
    db.session.commit()
    return jsonify({"message": "Appointment rescheduled", "appointment": appt.to_dict()}), 200


# ─── Cancel Appointment ───────────────────────────────────────────────────────

@appointment_bp.route("/<int:appt_id>/cancel", methods=["DELETE"])
@jwt_required()
def cancel_appointment(appt_id):
    claims = get_jwt()
    if claims.get("role") not in ("patient", "admin"):
        return jsonify({"error": "Access denied"}), 403

    appt = Appointment.query.get_or_404(appt_id)

    if claims.get("role") == "patient":
        patient = get_patient_profile()
        if appt.patient_id != patient.id:
            return jsonify({"error": "Unauthorized"}), 403

    if appt.status == "completed":
        return jsonify({"error": "Cannot cancel a completed appointment"}), 400
    if appt.status == "cancelled":
        return jsonify({"error": "Appointment is already cancelled"}), 400

    appt.status = "cancelled"
    db.session.commit()
    return jsonify({"message": "Appointment cancelled"}), 200


# ─── Doctor Availability ──────────────────────────────────────────────────────

@appointment_bp.route("/availability/<int:doctor_id>", methods=["GET"])
@jwt_required()
def doctor_availability(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)

    # Filter out slots already booked
    avail = dict(doctor.availability or {})
    booked_appts = Appointment.query.filter_by(doctor_id=doctor_id, status="booked").all()

    booked_slots = {}
    for a in booked_appts:
        booked_slots.setdefault(a.date, set()).add(a.time)

    free_slots = {}
    for d, slots in avail.items():
        free = [s for s in slots if s not in booked_slots.get(d, set())]
        if free:
            free_slots[d] = free

    return jsonify({
        "doctor_id": doctor_id,
        "doctor_name": doctor.user.username if doctor.user else None,
        "availability": free_slots,
    }), 200
