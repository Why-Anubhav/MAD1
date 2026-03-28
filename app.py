import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, send_from_directory
from flask_jwt_extended import JWTManager
from config import config_map
from extensions import db, migrate, bcrypt, cors, mail

# Import all models so SQLAlchemy knows about them
from models import User, Doctor, Patient, Department, Appointment, Treatment  # noqa: F401

# Import blueprints
from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
from routes.doctor_routes import doctor_bp
from routes.patient_routes import patient_bp
from routes.appointment_routes import appointment_bp


def create_app(env="default"):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "frontend"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "frontend"),
        static_url_path="",
    )

    # Load config
    app.config.from_object(config_map[env])

    # Create exports directory
    os.makedirs(app.config.get("EXPORT_DIR", os.path.join(os.path.dirname(__file__), "exports")), exist_ok=True)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    mail.init_app(app)

    jwt = JWTManager(app)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(doctor_bp, url_prefix="/api/doctor")
    app.register_blueprint(patient_bp, url_prefix="/api/patient")
    app.register_blueprint(appointment_bp, url_prefix="/api/appointment")

    # Serve the Vue SPA for all non-API routes
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
        if path and os.path.exists(os.path.join(frontend_dir, path)):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, "index.html")

    # Exports download route
    @app.route("/api/exports/<filename>")
    def download_export(filename):
        export_dir = app.config.get("EXPORT_DIR", os.path.join(os.path.dirname(__file__), "exports"))
        return send_from_directory(export_dir, filename, as_attachment=True)

    with app.app_context():
        db.create_all()
        _seed_initial_data()

    return app


def _seed_initial_data():
    """Seed admin user and default departments on first run."""
    from extensions import bcrypt as _bcrypt

    # Seed departments
    default_departments = [
        {"name": "Cardiology", "description": "Heart and cardiovascular system"},
        {"name": "Neurology", "description": "Brain and nervous system disorders"},
        {"name": "Orthopedics", "description": "Bone, joint and musculoskeletal conditions"},
        {"name": "Pediatrics", "description": "Medical care for infants and children"},
        {"name": "Dermatology", "description": "Skin, hair, and nail conditions"},
        {"name": "General Medicine", "description": "Primary and preventive care"},
        {"name": "Gynecology", "description": "Female reproductive health"},
        {"name": "Ophthalmology", "description": "Eye and vision care"},
    ]
    for dept_data in default_departments:
        if not Department.query.filter_by(name=dept_data["name"]).first():
            dept = Department(**dept_data)
            db.session.add(dept)

    # Seed admin user
    if not User.query.filter_by(username="admin").first():
        hashed = _bcrypt.generate_password_hash("admin123").decode("utf-8")
        admin = User(
            username="admin",
            password=hashed,
            role="admin",
            email="admin@hms.com",
            phone="0000000000",
            is_active=True,
        )
        db.session.add(admin)

    db.session.commit()
    print("[HMS] Database initialized. Admin user: admin / admin123")


if __name__ == "__main__":
    app = create_app("development")
    app.run(debug=True, host="0.0.0.0", port=8080)
