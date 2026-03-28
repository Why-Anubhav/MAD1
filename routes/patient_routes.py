from flask import Blueprint, request, jsonify
from extensions import db
from models import Patient, User, Doctor, Department, Appointment, Treatment
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from utils.cache import get_cached, set_cache, invalidate_pattern
import json

patient_bp = Blueprint("patient", __name__)


def patient_required(claims=None):
    if claims is None:
        claims = get_jwt()
    return claims.get("role") in ("patient", "admin")


def get_patient_profile():
    user_id = int(get_jwt_identity())
    return Patient.query.filter_by(user_id=user_id).first()


# ─── Profile ──────────────────────────────────────────────────────────────────

@patient_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    claims = get_jwt()
    if not patient_required(claims):
        return jsonify({"error": "Access denied"}), 403

    patient = get_patient_profile()
    if not patient:
        return jsonify({"error": "Patient profile not found"}), 404
    return jsonify(patient.to_dict()), 200


@patient_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    claims = get_jwt()
    if not patient_required(claims):
        return jsonify({"error": "Access denied"}), 403

    patient = get_patient_profile()
    if not patient:
        return jsonify({"error": "Patient profile not found"}), 404

    data = request.get_json()
    if "age" in data:
        patient.age = data["age"]
    if "gender" in data:
        patient.gender = data["gender"]
    if "address" in data:
        patient.address = data["address"]
    if "phone" in data:
        patient.user.phone = data["phone"]
    if "email" in data:
        existing = User.query.filter_by(email=data["email"]).first()
        if existing and existing.id != patient.user_id:
            return jsonify({"error": "Email already in use"}), 409
        patient.user.email = data["email"]

    db.session.commit()
    return jsonify({"message": "Profile updated", "profile": patient.to_dict()}), 200


# ─── Doctors (with cache) ─────────────────────────────────────────────────────

@patient_bp.route("/doctors", methods=["GET"])
@jwt_required()
def get_doctors():
    search = request.args.get("search", "").strip()
    dept_id = request.args.get("department_id")

    cache_key = f"doctor_list_{search}_{dept_id}"
    cached = get_cached(cache_key)
    if cached:
        return jsonify(json.loads(cached)), 200

    query = Doctor.query.join(User).filter(User.is_active == True)
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (Doctor.specialization.ilike(f"%{search}%"))
        )
    if dept_id:
        query = query.filter(Doctor.department_id == int(dept_id))

    doctors = query.all()
    result = [d.to_dict() for d in doctors]
    set_cache(cache_key, json.dumps(result), timeout=300)
    return jsonify(result), 200


# ─── Departments (with cache) ─────────────────────────────────────────────────

@patient_bp.route("/departments", methods=["GET"])
@jwt_required()
def get_departments():
    cache_key = "department_list"
    cached = get_cached(cache_key)
    if cached:
        return jsonify(json.loads(cached)), 200

    departments = Department.query.all()
    result = [d.to_dict() for d in departments]
    set_cache(cache_key, json.dumps(result), timeout=600)
    return jsonify(result), 200


# ─── Treatment History ────────────────────────────────────────────────────────

@patient_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    claims = get_jwt()
    if not patient_required(claims):
        return jsonify({"error": "Access denied"}), 403

    patient = get_patient_profile()
    if not patient:
        return jsonify({"error": "Patient profile not found"}), 404

    history = []
    for appt in patient.appointments:
        entry = appt.to_dict()
        entry["treatment"] = appt.treatment.to_dict() if appt.treatment else None
        history.append(entry)

    history.sort(key=lambda x: (x["date"], x["time"]), reverse=True)
    return jsonify(history), 200


# ─── CSV Export (Celery task) ──────────────────────────────────────────────────

@patient_bp.route("/export", methods=["POST"])
@jwt_required()
def export_history():
    claims = get_jwt()
    if not patient_required(claims):
        return jsonify({"error": "Access denied"}), 403

    patient = get_patient_profile()
    if not patient:
        return jsonify({"error": "Patient profile not found"}), 404

    from tasks.celery_worker import export_patient_csv_task
    task = export_patient_csv_task.delay(patient.id, patient.user.email)
    return jsonify({
        "message": "CSV export started. You will be notified when it is ready.",
        "task_id": task.id,
    }), 202


@patient_bp.route("/export/status/<task_id>", methods=["GET"])
@jwt_required()
def export_status(task_id):
    from tasks.celery_worker import celery_app
    task = celery_app.AsyncResult(task_id)
    return jsonify({
        "task_id": task_id,
        "status": task.state,
        "result": task.result if task.state == "SUCCESS" else None,
    }), 200
