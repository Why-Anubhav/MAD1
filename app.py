"""
Placement Portal – Entry Point
Run: python app.py
"""

import os
import sys

# Ensure routes package is importable
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
from models import init_db
from routes.auth_routes    import auth_bp
from routes.admin_routes   import admin_bp
from routes.student_routes import student_bp
from routes.company_routes import company_bp

app = Flask(__name__)
app.secret_key = "placement_portal_secret_key_2024"

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(student_bp)
app.register_blueprint(company_bp)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
