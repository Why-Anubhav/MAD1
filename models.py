"""
Database models for the Placement Portal.
Uses SQLite via direct sqlite3 — tables are created programmatically.
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            email    TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL,
            role     TEXT    NOT NULL CHECK(role IN ('admin','student','company'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            branch          TEXT,
            cgpa            REAL,
            graduation_year INTEGER,
            resume_path     TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            company_name    TEXT    NOT NULL,
            hr_contact      TEXT,
            website         TEXT,
            approval_status TEXT    NOT NULL DEFAULT 'pending'
                            CHECK(approval_status IN ('pending','approved','rejected'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS placement_drives (
            drive_id             INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id           INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
            job_title            TEXT    NOT NULL,
            job_description      TEXT,
            eligibility          TEXT,
            package              TEXT,
            application_deadline TEXT,
            drive_status         TEXT    NOT NULL DEFAULT 'pending'
                                 CHECK(drive_status IN ('pending','approved','rejected'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            application_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id         INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
            drive_id           INTEGER NOT NULL REFERENCES placement_drives(drive_id) ON DELETE CASCADE,
            application_date   TEXT    NOT NULL,
            application_status TEXT    NOT NULL DEFAULT 'Applied'
                               CHECK(application_status IN ('Applied','Shortlisted','Selected','Rejected')),
            UNIQUE(student_id, drive_id)
        )
    """)

    existing = c.execute("SELECT id FROM users WHERE role='admin'").fetchone()
    if not existing:
        c.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
            ("Admin", "admin@portal.com", generate_password_hash("admin123"), "admin"),
        )

    conn.commit()
    conn.close()
    print("Database initialised.")
