# LeaveDesk API

Employee Leave and Work From Home Management System built using Python, FastAPI, PostgreSQL, and SQLAlchemy.

## Features

- JWT-based authentication
- Role-based access control (Employee and Manager)
- Leave request creation, validation, and cancellation
- Work From Home request management
- Manager approval and rejection workflows
- CSV leave reports
- Database health check
- Automated tests using Pytest

## Technology Stack

- Python 3.11
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- JWT Authentication
- Pytest

## Project Status

All automated tests are passing (approximately 62 test cases).

## Prerequisites

- Python 3.11 or later
- PostgreSQL 15 or later
- Git

## Installation

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd LeaveDesk
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env`:

Windows PowerShell:
```powershell
Copy-Item .env.example .env
```

Update the database URL and secret key in `.env`.

### 5. Create the PostgreSQL database

Create a database named `leavedesk_dev` in PostgreSQL.

### 6. Initialize database tables

```bash
alembic upgrade head
```

### 7. Seed initial users

```bash
python seed.py
```

### 8. Start the application

```bash
uvicorn app.main:app --reload
```

## API Documentation

Once the application is running, open:

- Swagger UI: http://127.0.0.1:8000/docs
- Health Check: http://127.0.0.1:8000/health

## Running Tests

Configure a separate PostgreSQL test database using `TEST_DATABASE_URL` in `.env`.

Run all tests:

```bash
python -m pytest -v
```

## Project Structure

```text
LeaveDesk/
│
├── alembic/
│   ├── versions/
│   │   └── <initial_migration>.py
│   ├── env.py
│   ├── README
│   └── script.py.mako
│
├── app/
│   ├── api/
│   │   ├── auth.py
│   │   ├── leaves.py
│   │   ├── wfh.py
│   │   ├── manager.py
│   │   ├── reports.py
│   │   └── health.py
│   │
│   ├── core/
│   │   ├── auth.py
│   │   ├── config.py
│   │   └── security.py
│   │
│   ├── db/
│   │   ├── session.py
│   │   └── dependencies.py
│   │
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
│
├── tests/
│
├── .env
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
├── seed.py
├── README.md
└── project_structure.txt
```

**Note:** `.env` is shown to describe your local setup, but it must never be committed to GitHub.
```


## Design Assumptions

- Employees can manage only their own leave and WFH requests.
- Managers can access requests belonging only to their direct reports.
- Only pending requests can be cancelled, approved, or rejected.
- A rejection requires a comment of at least five characters.
- A full-day leave conflicts with any other active leave on the same date.
- Two half-day requests can coexist when they cover different halves.
- An hours-based leave request cannot overlap another active request on the same date.
- WFH requests can cover a maximum of two working days.
- Saturdays and Sundays are excluded when calculating WFH working days.
- Public holidays are not excluded from WFH calculations.

## Testing

The project uses Pytest and FastAPI TestClient for automated testing.

Test coverage includes:

- Authentication and JWT validation
- Leave request creation and validation
- Leave cancellation and overlap detection
- WFH request creation and cancellation
- Manager authorization and approval workflows
- CSV report generation
- Database health checks
- Invalid requests and access restrictions

Run all tests:

```bash
python -m pytest -v
```

Current test result: Approximately 62 tests passed.

## Future Improvements

- Add email notifications for leave approvals and rejections.
- Introduce pagination for request listing APIs.
- Add structured application logging.
- Improve API performance and database query optimization.
- Add Docker support for easier deployment.
- Implement more detailed audit logs.

## Security Notes

- Passwords are stored using bcrypt hashing.
- API authentication uses JWT bearer tokens.
- Role-based authorization restricts manager operations.
- Environment variables are used for sensitive configuration.
- The `.env` file must not be committed to version control.
