# PlaceHub – Campus Placement Portal

A complete Flask web application for managing campus recruitment.

## Quick Start

```bash
pip install flask werkzeug
python app.py
```

Visit: http://localhost:5000

## Default Admin Credentials
- Email: admin@portal.com
- Password: admin123

## User Roles
| Role    | Registration | Login Condition            |
|---------|-------------|---------------------------|
| Admin   | Pre-seeded  | Direct                    |
| Student | Self-register | Immediate login           |
| Company | Self-register | After admin approval      |

## Features
- Admin: approve/reject companies & drives, view all students/applications, search
- Company: post/edit drives, view applicants, update application status
- Student: browse approved drives, apply (once), upload resume, track status
