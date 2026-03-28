from datetime import datetime
from extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin / doctor / patient
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    doctor_profile = db.relationship("Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    patient_profile = db.relationship("Patient", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "email": self.email,
            "phone": self.phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
        }


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    doctors = db.relationship("Doctor", back_populates="department")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    specialization = db.Column(db.String(150), nullable=False)
    availability = db.Column(db.JSON, nullable=True, default=dict)  # {date: [time_slots]}
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)

    user = db.relationship("User", back_populates="doctor_profile")
    department = db.relationship("Department", back_populates="doctors")
    appointments = db.relationship("Appointment", back_populates="doctor")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "email": self.user.email if self.user else None,
            "phone": self.user.phone if self.user else None,
            "is_active": self.user.is_active if self.user else True,
            "specialization": self.specialization,
            "availability": self.availability or {},
            "department_id": self.department_id,
            "department": self.department.name if self.department else None,
        }


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)

    user = db.relationship("User", back_populates="patient_profile")
    appointments = db.relationship("Appointment", back_populates="patient")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "email": self.user.email if self.user else None,
            "phone": self.user.phone if self.user else None,
            "is_active": self.user.is_active if self.user else True,
            "age": self.age,
            "gender": self.gender,
            "address": self.address,
        }


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    date = db.Column(db.String(20), nullable=False)   # YYYY-MM-DD
    time = db.Column(db.String(10), nullable=False)   # HH:MM
    status = db.Column(db.String(20), default="booked")  # booked / completed / cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship("Patient", back_populates="appointments")
    doctor = db.relationship("Doctor", back_populates="appointments")
    treatment = db.relationship("Treatment", back_populates="appointment", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "patient_name": self.patient.user.username if self.patient and self.patient.user else None,
            "doctor_name": self.doctor.user.username if self.doctor and self.doctor.user else None,
            "doctor_specialization": self.doctor.specialization if self.doctor else None,
            "department": self.doctor.department.name if self.doctor and self.doctor.department else None,
            "date": self.date,
            "time": self.time,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Treatment(db.Model):
    __tablename__ = "treatments"

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=False)
    diagnosis = db.Column(db.Text, nullable=True)
    prescription = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointment = db.relationship("Appointment", back_populates="treatment")

    def to_dict(self):
        appt = self.appointment
        return {
            "id": self.id,
            "appointment_id": self.appointment_id,
            "patient_name": appt.patient.user.username if appt and appt.patient and appt.patient.user else None,
            "doctor_name": appt.doctor.user.username if appt and appt.doctor and appt.doctor.user else None,
            "date": appt.date if appt else None,
            "time": appt.time if appt else None,
            "diagnosis": self.diagnosis,
            "prescription": self.prescription,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
