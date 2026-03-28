from flask import Blueprint, request, jsonify
from extensions import db, bcrypt
from models import User, Patient
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from datetime import datetime

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required"}), 400

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not bcrypt.check_password_hash(user.password, data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_active:
        return jsonify({"error": "Account has been deactivated. Contact admin."}), 403

    additional_claims = {"role": user.role, "user_id": user.id}
    token = create_access_token(identity=str(user.id), additional_claims=additional_claims)

    profile_id = None
    if user.role == "doctor" and user.doctor_profile:
        profile_id = user.doctor_profile.id
    elif user.role == "patient" and user.patient_profile:
        profile_id = user.patient_profile.id

    return jsonify({
        "access_token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email,
            "profile_id": profile_id,
        }
    }), 200


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    required = ["username", "password", "email"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already taken"}), 409
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409

    hashed = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    user = User(
        username=data["username"],
        password=hashed,
        role="patient",
        email=data["email"],
        phone=data.get("phone", ""),
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.session.add(user)
    db.session.flush()

    patient = Patient(
        user_id=user.id,
        age=data.get("age"),
        gender=data.get("gender", ""),
        address=data.get("address", ""),
    )
    db.session.add(patient)
    db.session.commit()

    return jsonify({"message": "Registration successful. You can now login."}), 201


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    return jsonify({"message": "Logged out successfully"}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict()), 200
