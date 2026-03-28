from flask import Blueprint, request, jsonify
from extensions import db, bcrypt
from models import User, Doctor, Patient, Department, Appointment
from flask_jwt_extended import jwt_required, get_jwt
from utils.cache import invalidate_pattern
from datetime import datetime

admin_bp = Blueprint("admin", __name__)


def admin_required():
    claims = get_jwt()
    if claims.get("role") != "admin":
        return False
    return True


# ─── Stats ────────────────────────────────────────────────────────────────────

@admin_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    total_doctors = Doctor.query.count()
    total_patients = Patient.query.count()
    total_appointments = Appointment.query.count()
    booked = Appointment.query.filter_by(status="booked").count()
    completed = Appointment.query.filter_by(status="completed").count()
    cancelled = Appointment.query.filter_by(status="cancelled").count()

    # Appointments per department
    dept_stats = []
    departments = Department.query.all()
    for dept in departments:
        count = (
            Appointment.query
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .filter(Doctor.department_id == dept.id)
            .count()
        )
        dept_stats.append({"department": dept.name, "count": count})

    # Appointments per doctor (top 10)
    doctor_stats = []
    doctors = Doctor.query.all()
    for doc in doctors:
        count = Appointment.query.filter_by(doctor_id=doc.id).count()
        doctor_stats.append({
            "doctor": doc.user.username if doc.user else "Unknown",
            "count": count,
        })
    doctor_stats = sorted(doctor_stats, key=lambda x: x["count"], reverse=True)[:10]

    return jsonify({
        "total_doctors": total_doctors,
        "total_patients": total_patients,
        "total_appointments": total_appointments,
        "booked": booked,
        "completed": completed,
        "cancelled": cancelled,
        "dept_stats": dept_stats,
        "doctor_stats": doctor_stats,
    }), 200


# ─── Doctors ──────────────────────────────────────────────────────────────────

@admin_bp.route("/doctors", methods=["GET"])
@jwt_required()
def list_doctors():
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    search = request.args.get("search", "").strip()
    query = Doctor.query.join(User)
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (Doctor.specialization.ilike(f"%{search}%"))
        )
    doctors = query.all()
    return jsonify([d.to_dict() for d in doctors]), 200


@admin_bp.route("/doctors", methods=["POST"])
@jwt_required()
def add_doctor():
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    data = request.get_json()
    required = ["username", "password", "email", "specialization"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"{f} is required"}), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already taken"}), 409
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409

    hashed = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    user = User(
        username=data["username"],
        password=hashed,
        role="doctor",
        email=data["email"],
        phone=data.get("phone", ""),
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.session.add(user)
    db.session.flush()

    doctor = Doctor(
        user_id=user.id,
        specialization=data["specialization"],
        department_id=data.get("department_id"),
        availability={},
    )
    db.session.add(doctor)
    db.session.commit()
    invalidate_pattern("doctor_list*")
    return jsonify({"message": "Doctor added successfully", "doctor": doctor.to_dict()}), 201


@admin_bp.route("/doctors/<int:doctor_id>", methods=["PUT"])
@jwt_required()
def update_doctor(doctor_id):
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    doctor = Doctor.query.get_or_404(doctor_id)
    data = request.get_json()

    if "specialization" in data:
        doctor.specialization = data["specialization"]
    if "department_id" in data:
        doctor.department_id = data["department_id"]
    if "phone" in data:
        doctor.user.phone = data["phone"]
    if "email" in data:
        existing = User.query.filter_by(email=data["email"]).first()
        if existing and existing.id != doctor.user_id:
            return jsonify({"error": "Email already in use"}), 409
        doctor.user.email = data["email"]

    db.session.commit()
    invalidate_pattern("doctor_list*")
    return jsonify({"message": "Doctor updated", "doctor": doctor.to_dict()}), 200


@admin_bp.route("/doctors/<int:doctor_id>", methods=["DELETE"])
@jwt_required()
def delete_doctor(doctor_id):
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    doctor = Doctor.query.get_or_404(doctor_id)
    user = doctor.user
    db.session.delete(doctor)
    db.session.delete(user)
    db.session.commit()
    invalidate_pattern("doctor_list*")
    return jsonify({"message": "Doctor deleted"}), 200


# ─── Patients ─────────────────────────────────────────────────────────────────

@admin_bp.route("/patients", methods=["GET"])
@jwt_required()
def list_patients():
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    search = request.args.get("search", "").strip()
    query = Patient.query.join(User)
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )
    patients = query.all()
    return jsonify([p.to_dict() for p in patients]), 200


# ─── Appointments ─────────────────────────────────────────────────────────────

@admin_bp.route("/appointments", methods=["GET"])
@jwt_required()
def list_appointments():
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    status = request.args.get("status")
    query = Appointment.query
    if status:
        query = query.filter_by(status=status)
    appointments = query.order_by(Appointment.date.desc(), Appointment.time.desc()).all()
    return jsonify([a.to_dict() for a in appointments]), 200


# ─── Blacklist ────────────────────────────────────────────────────────────────

@admin_bp.route("/blacklist/<int:user_id>", methods=["POST"])
@jwt_required()
def toggle_blacklist(user_id):
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        return jsonify({"error": "Cannot deactivate admin"}), 400
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    invalidate_pattern("doctor_list*")
    return jsonify({"message": f"User {status}", "is_active": user.is_active}), 200


# ─── Departments ──────────────────────────────────────────────────────────────

@admin_bp.route("/departments", methods=["GET"])
@jwt_required()
def list_departments():
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    departments = Department.query.all()
    return jsonify([d.to_dict() for d in departments]), 200


@admin_bp.route("/departments", methods=["POST"])
@jwt_required()
def add_department():
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403

    data = request.get_json()
    if not data.get("name"):
        return jsonify({"error": "Department name is required"}), 400

    if Department.query.filter_by(name=data["name"]).first():
        return jsonify({"error": "Department already exists"}), 409

    dept = Department(name=data["name"], description=data.get("description", ""))
    db.session.add(dept)
    db.session.commit()
    return jsonify({"message": "Department added", "department": dept.to_dict()}), 201
