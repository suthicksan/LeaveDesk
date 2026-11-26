import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import timedelta

from dotenv import load_dotenv

from app.main import app
from app.db.session import Base
from app.db.dependencies import get_db

# Import all models so SQLAlchemy registers their tables
from app.models.user import User
from app.models.leave import LeaveRequest
from app.models.wfh import WFHRequest
from app.core.security import get_password_hash, create_access_token


load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    raise ValueError("TEST_DATABASE_URL is missing from .env")

test_engine = create_engine(TEST_DATABASE_URL)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    # Create tables in the separate test database
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    # Clean up tables after the test session
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()

    session = TestingSessionLocal(
        bind=connection,
        join_transaction_mode="create_savepoint"
    )

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def seed_users(db_session):
    manager = User(
        name="Priya Manager",
        email="priya.manager@leavedesk.test",
        hashed_password=get_password_hash("Manager@123"),
        role="manager",
        manager_id=None
    )

    db_session.add(manager)
    db_session.flush()

    employee = User(
        name="Arjun Employee",
        email="arjun@leavedesk.test",
        hashed_password=get_password_hash("Employee@123"),
        role="employee",
        manager_id=manager.id
    )

    other_employee = User(
        name="Meera Employee",
        email="meera@leavedesk.test",
        hashed_password=get_password_hash("Employee@123"),
        role="employee",
        manager_id=manager.id
    )

    db_session.add_all([employee, other_employee])
    db_session.commit()

    return {
        "manager": manager,
        "employee": employee,
        "other_employee": other_employee
    }


def test_login_success(client, seed_users):
    response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, seed_users):
    response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "WrongPassword123"
        }
    )

    assert response.status_code == 401

def test_get_current_user(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Arjun Employee"
    assert data["email"] == "arjun@leavedesk.test"
    assert data["role"] == "employee"
    assert "hashed_password" not in data

def test_expired_token(client, seed_users):
    user = seed_users["employee"]

    expired_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=-1)
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {expired_token}"
        }
    )

    assert response.status_code == 401

def test_employee_cannot_access_manager_requests(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.get(
        "/manager/requests",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 403

def test_create_leave_success(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-12-10",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Personal work"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["leave_type"] == "CASUAL"
    assert data["duration_type"] == "FULL_DAY"
    assert data["days_counted"] == "1.00" or data["days_counted"] == 1
    assert data["status"] == "PENDING"

def test_create_leave_invalid_duration(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-12-11",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "half": "FIRST_HALF",
            "reason": "Invalid duration test"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 422

def test_create_half_day_leave(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-12-12",
            "leave_type": "SICK",
            "duration_type": "HALF_DAY",
            "half": "FIRST_HALF",
            "reason": "Medical appointment"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["duration_type"] == "HALF_DAY"
    assert data["half"] == "FIRST_HALF"
    assert data["days_counted"] == "0.50" or data["days_counted"] == 0.5

def test_create_hours_leave(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-12-14",
            "leave_type": "CASUAL",
            "duration_type": "HOURS",
            "hours": 2,
            "reason": "Personal appointment"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["duration_type"] == "HOURS"
    assert data["hours"] == 2
    assert data["days_counted"] == "0.25" or data["days_counted"] == 0.25

def test_create_leave_invalid_hours(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-12-15",
            "leave_type": "CASUAL",
            "duration_type": "HOURS",
            "hours": 4,
            "reason": "Invalid hours test"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 422

def test_duplicate_leave_returns_conflict(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    leave_data = {
        "leave_date": "2026-12-16",
        "leave_type": "CASUAL",
        "duration_type": "FULL_DAY",
        "reason": "Personal work"
    }

    first_response = client.post(
        "/leaves",
        json=leave_data,
        headers=headers
    )

    second_response = client.post(
        "/leaves",
        json=leave_data,
        headers=headers
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_cancel_pending_leave(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    leave_response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-12-17",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Cancellation test"
        },
        headers=headers
    )

    leave_id = leave_response.json()["id"]

    cancel_response = client.post(
        f"/leaves/{leave_id}/cancel",
        headers=headers
    )

    assert leave_response.status_code == 201
    assert cancel_response.status_code == 200
    assert cancel_response.json()["message"] == (
        "Leave request cancelled successfully"
    )

    # Verify the updated status through the employee's leave list
    list_response = client.get(
        "/leaves/me",
        headers=headers
    )

    assert list_response.status_code == 200

    cancelled_leave = next(
        item for item in list_response.json()
        if item["id"] == leave_id
    )

    assert cancelled_leave["status"] == "CANCELLED"

def test_employee_cannot_cancel_another_users_leave(client, seed_users):
    # Login as Arjun
    arjun_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    arjun_token = arjun_login.json()["access_token"]

    # Login as Meera
    meera_login = client.post(
        "/auth/login",
        json={
            "email": "meera@leavedesk.test",
            "password": "Employee@123"
        }
    )
    meera_token = meera_login.json()["access_token"]

    # Meera creates a leave request
    leave_response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-12-18",
            "leave_type": "SICK",
            "duration_type": "FULL_DAY",
            "reason": "Medical appointment"
        },
        headers={
            "Authorization": f"Bearer {meera_token}"
        }
    )

    leave_id = leave_response.json()["id"]

    # Arjun attempts to cancel Meera's request
    cancel_response = client.post(
        f"/leaves/{leave_id}/cancel",
        headers={
            "Authorization": f"Bearer {arjun_token}"
        }
    )

    assert leave_response.status_code == 201
    assert cancel_response.status_code == 404

def test_create_wfh_success(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/wfh",
        json={
            "start_date": "2026-12-21",
            "end_date": "2026-12-22",
            "reason": "Working on project tasks"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["start_date"] == "2026-12-21"
    assert data["end_date"] == "2026-12-22"
    assert data["status"] == "PENDING"
    assert data["reason"] == "Working on project tasks"

def test_create_wfh_exceeds_two_working_days(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/wfh",
        json={
            "start_date": "2026-12-21",
            "end_date": "2026-12-23",
            "reason": "Three working days"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 422

def test_create_wfh_invalid_date_range(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/wfh",
        json={
            "start_date": "2026-12-23",
            "end_date": "2026-12-21",
            "reason": "Invalid date range"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 422

def test_create_wfh_weekend_only(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]

    response = client.post(
        "/wfh",
        json={
            "start_date": "2026-12-26",
            "end_date": "2026-12-27",
            "reason": "Weekend WFH test"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 422

def test_duplicate_wfh_returns_conflict(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    wfh_data = {
        "start_date": "2026-12-28",
        "end_date": "2026-12-29",
        "reason": "WFH overlap test"
    }

    first_response = client.post(
        "/wfh",
        json=wfh_data,
        headers=headers
    )

    second_response = client.post(
        "/wfh",
        json=wfh_data,
        headers=headers
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409

def test_wfh_conflicts_with_full_day_leave(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    leave_response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-12-30",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Personal work"
        },
        headers=headers
    )

    assert leave_response.status_code == 201

    wfh_response = client.post(
        "/wfh",
        json={
            "start_date": "2026-12-30",
            "end_date": "2026-12-31",
            "reason": "Work from home"
        },
        headers=headers
    )

    assert wfh_response.status_code == 409

def test_cancel_pending_wfh(client, seed_users):
    login_response = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2027-01-04",
            "end_date": "2027-01-04",
            "reason": "Personal requirement"
        },
        headers=headers
    )
    assert create_response.status_code == 201

    wfh_id = create_response.json()["id"]

    cancel_response = client.post(
        f"/wfh/{wfh_id}/cancel",
        headers=headers
    )
    assert cancel_response.status_code == 200

    list_response = client.get("/wfh/me", headers=headers)
    assert list_response.status_code == 200

    cancelled_request = next(
        item for item in list_response.json()
        if item["id"] == wfh_id
    )
    assert cancelled_request["status"] == "CANCELLED"

def test_employee_cannot_cancel_another_users_wfh(client, seed_users):
    # Meera logs in and creates a WFH request
    meera_login = client.post(
        "/auth/login",
        json={
            "email": "meera@leavedesk.test",
            "password": "Employee@123"
        }
    )
    meera_token = meera_login.json()["access_token"]
    meera_headers = {"Authorization": f"Bearer {meera_token}"}

    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2027-01-05",
            "end_date": "2027-01-05",
            "reason": "Personal requirement"
        },
        headers=meera_headers
    )
    assert create_response.status_code == 201
    wfh_id = create_response.json()["id"]

    # Arjun tries to cancel Meera's request
    arjun_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    arjun_token = arjun_login.json()["access_token"]
    arjun_headers = {"Authorization": f"Bearer {arjun_token}"}

    cancel_response = client.post(
        f"/wfh/{wfh_id}/cancel",
        headers=arjun_headers
    )

    assert cancel_response.status_code == 404 
def test_cannot_cancel_approved_wfh(client, seed_users):
    # Employee creates a WFH request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_token = employee_login.json()["access_token"]
    employee_headers = {
        "Authorization": f"Bearer {employee_token}"
    }

    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2027-01-06",
            "end_date": "2027-01-06",
            "reason": "Personal requirement"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    wfh_id = create_response.json()["id"]

    # Manager approves the request
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_token = manager_login.json()["access_token"]
    manager_headers = {
        "Authorization": f"Bearer {manager_token}"
    }

    approve_response = client.post(
    f"/manager/wfh/{wfh_id}/approve",
    json={},
    headers=manager_headers
    )
    print("Approval response:", approve_response.status_code, approve_response.json())
    assert approve_response.status_code == 200

    # Employee tries to cancel the approved request
    cancel_response = client.post(
        f"/wfh/{wfh_id}/cancel",
        headers=employee_headers
    )
    assert cancel_response.status_code == 409

def test_manager_rejects_wfh_with_comment(client, seed_users):
    # Employee creates a WFH request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2027-01-07",
            "end_date": "2027-01-07",
            "reason": "Personal requirement"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    wfh_id = create_response.json()["id"]

    # Manager rejects the request
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    reject_response = client.post(
        f"/manager/wfh/{wfh_id}/reject",
        json={"comment": "Insufficient project coverage"},
        headers=manager_headers
    )

    assert reject_response.status_code == 200

    list_response = client.get("/wfh/me", headers=employee_headers)
    assert list_response.status_code == 200

    rejected_request = next(
    item for item in list_response.json()
    if item["id"] == wfh_id
    )

    assert rejected_request["status"] == "REJECTED"
    assert rejected_request["decision_comment"] == "Insufficient project coverage"

def test_manager_can_view_team_requests(client, seed_users):
    # Arjun creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    leave_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-01-08",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Personal work"
        },
        headers=employee_headers
    )
    assert leave_response.status_code == 201

    # Priya views her team's requests
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    response = client.get(
        "/manager/requests",
        headers=manager_headers
    )

    assert response.status_code == 200
    requests = response.json()
    assert any(
        item["employee_id"] == seed_users["employee"].id
        and item["request_type"] == "LEAVE"
        for item in requests
    )

def test_manager_can_filter_pending_requests(client, seed_users):
    # Arjun creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-01-11",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Pending filter test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201

    # Manager filters pending requests
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    response = client.get(
        "/manager/requests",
        params={"status_filter": "PENDING"},
        headers=manager_headers
    )

    assert response.status_code == 200
    requests = response.json()
    assert len(requests) >= 1
    assert all(item["status"] == "PENDING" for item in requests)

def test_manager_can_filter_requests_by_employee_id(client, seed_users):
    # Arjun creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-01-12",
            "leave_type": "SICK",
            "duration_type": "FULL_DAY",
            "reason": "Employee filter test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201

    # Manager filters by Arjun's employee ID
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    response = client.get(
        "/manager/requests",
        params={"employee_id": seed_users["employee"].id},
        headers=manager_headers
    )

    assert response.status_code == 200
    requests = response.json()
    assert len(requests) >= 1
    assert all(
        item["employee_id"] == seed_users["employee"].id
        for item in requests
    )

def test_manager_can_filter_requests_by_date_range(client, seed_users):
    # Arjun creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-01-15",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Date filter test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201

    # Manager requests only leave requests within the date range
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    response = client.get(
        "/manager/requests",
        params={
            "from_date": "2027-01-10",
            "to_date": "2027-01-20"
        },
        headers=manager_headers
    )

    assert response.status_code == 200
    requests = response.json()
    # print("MANAGER RESPONSE:", requests)
    assert len(requests) >= 1
    assert all(
        "2027-01-10" <= item["leave_date"][:10] <= "2027-01-20"
        for item in requests
    )

def test_manager_can_approve_leave(client, seed_users):
    # Arjun logs in and creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-01-25",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Approval test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    leave_id = create_response.json()["id"]

    # Priya logs in as manager and approves the request
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    approval_response = client.post(
        f"/manager/leaves/{leave_id}/approve",
        json={},
        headers=manager_headers
    )

    assert approval_response.status_code == 200

    # Verify the updated status from Arjun's leave list
    response = client.get("/leaves/me", headers=employee_headers)

    assert response.status_code == 200
    approved_leave = next(
        item for item in response.json()
        if item["id"] == leave_id
    )
    assert approved_leave["status"] == "APPROVED"

def test_manager_can_reject_leave_with_comment(client, seed_users):
    # Arjun creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-01-26",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Rejection test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    leave_id = create_response.json()["id"]

    # Priya rejects the leave request
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    rejection_response = client.post(
        f"/manager/leaves/{leave_id}/reject",
        json={"comment": "Insufficient team coverage"},
        headers=manager_headers
    )

    assert rejection_response.status_code == 200

    # Verify the employee sees the rejected status and comment
    response = client.get("/leaves/me", headers=employee_headers)

    assert response.status_code == 200
    rejected_leave = next(
        item for item in response.json()
        if item["id"] == leave_id
    )
    assert rejected_leave["status"] == "REJECTED"

def test_manager_can_approve_wfh(client, seed_users):
    # Arjun creates a WFH request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2027-02-01",
            "end_date": "2027-02-01",
            "reason": "WFH approval test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    wfh_id = create_response.json()["id"]

    # Priya approves the WFH request
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    approval_response = client.post(
        f"/manager/wfh/{wfh_id}/approve",
        json={},
        headers=manager_headers
    )
    assert approval_response.status_code == 200

    # Verify the updated status
    response = client.get("/wfh/me", headers=employee_headers)

    assert response.status_code == 200
    approved_wfh = next(
        item for item in response.json()
        if item["id"] == wfh_id
    )
    assert approved_wfh["status"] == "APPROVED"

def test_manager_can_reject_wfh_with_comment(client, seed_users):
    # Arjun creates a WFH request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2027-02-02",
            "end_date": "2027-02-02",
            "reason": "WFH rejection test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    wfh_id = create_response.json()["id"]

    # Priya rejects the WFH request
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    rejection_response = client.post(
        f"/manager/wfh/{wfh_id}/reject",
        json={"comment": "Insufficient project coverage"},
        headers=manager_headers
    )
    assert rejection_response.status_code == 200

    # Verify the employee sees the rejected status
    response = client.get("/wfh/me", headers=employee_headers)

    assert response.status_code == 200
    rejected_wfh = next(
        item for item in response.json()
        if item["id"] == wfh_id
    )
    assert rejected_wfh["status"] == "REJECTED"

def test_manager_cannot_approve_already_approved_leave(client, seed_users):
    # Arjun creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-02-10",
            "leave_type": "SICK",
            "duration_type": "FULL_DAY",
            "reason": "Already approved test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    leave_id = create_response.json()["id"]

    # Priya logs in
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    # First approval should succeed
    first_response = client.post(
        f"/manager/leaves/{leave_id}/approve",
        json={},
        headers=manager_headers
    )
    assert first_response.status_code == 200

    # Second approval should fail with 409 Conflict
    second_response = client.post(
        f"/manager/leaves/{leave_id}/approve",
        json={},
        headers=manager_headers
    )
    assert second_response.status_code == 409

def test_manager_cannot_approve_already_approved_wfh(client, seed_users):
    # Arjun creates a WFH request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2027-02-15",
            "end_date": "2027-02-15",
            "reason": "Already approved WFH test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    wfh_id = create_response.json()["id"]

    # Priya logs in as manager
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    # First approval should succeed
    first_response = client.post(
        f"/manager/wfh/{wfh_id}/approve",
        json={},
        headers=manager_headers
    )
    assert first_response.status_code == 200

    # Second approval should return 409 Conflict
    second_response = client.post(
        f"/manager/wfh/{wfh_id}/approve",
        json={},
        headers=manager_headers
    )
    assert second_response.status_code == 409

def test_manager_cannot_reject_leave_with_short_comment(client, seed_users):
    # Arjun creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-02-20",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Short comment validation test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    leave_id = create_response.json()["id"]

    # Priya logs in as manager
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    # Rejecting with fewer than 5 characters should fail
    rejection_response = client.post(
        f"/manager/leaves/{leave_id}/reject",
        json={"comment": "Bad"},
        headers=manager_headers
    )

    assert rejection_response.status_code == 422

def test_manager_cannot_reject_wfh_with_short_comment(client, seed_users):
    # Arjun creates a WFH request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2027-02-22",
            "end_date": "2027-02-22",
            "reason": "Short comment validation test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    wfh_id = create_response.json()["id"]

    # Priya logs in as manager
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    # Rejecting with fewer than 5 characters should fail
    rejection_response = client.post(
        f"/manager/wfh/{wfh_id}/reject",
        json={"comment": "Bad"},
        headers=manager_headers
    )

    assert rejection_response.status_code == 422


def test_manager_cannot_approve_other_teams_leave(client, seed_users, db_session):
    # Create a second manager
    second_manager = User(
        name="Second Manager",
        email="second.manager@leavedesk.test",
        hashed_password=get_password_hash("Manager@456"),
        role="manager",
        manager_id=None
    )
    db_session.add(second_manager)
    db_session.flush()

    # Create an employee reporting to the second manager
    second_employee = User(
        name="Other Team Employee",
        email="other.employee@leavedesk.test",
        hashed_password=get_password_hash("Employee@456"),
        role="employee",
        manager_id=second_manager.id
    )
    db_session.add(second_employee)
    db_session.commit()

    # Other employee creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "other.employee@leavedesk.test",
            "password": "Employee@456"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-03-01",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Cross-team access test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    leave_id = create_response.json()["id"]

    # Priya (first manager) tries to approve the other team's request
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    approval_response = client.post(
        f"/manager/leaves/{leave_id}/approve",
        json={},
        headers=manager_headers
    )

    assert approval_response.status_code == 403

def test_manager_cannot_approve_other_teams_wfh(client, seed_users, db_session):
    # Create a second manager
    second_manager = User(
        name="Second Manager",
        email="second.manager@leavedesk.test",
        hashed_password=get_password_hash("Manager@456"),
        role="manager",
        manager_id=None
    )
    db_session.add(second_manager)
    db_session.flush()

    # Create an employee reporting to the second manager
    second_employee = User(
        name="Other Team Employee",
        email="other.employee@leavedesk.test",
        hashed_password=get_password_hash("Employee@456"),
        role="employee",
        manager_id=second_manager.id
    )
    db_session.add(second_employee)
    db_session.commit()

    # Other employee creates a WFH request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "other.employee@leavedesk.test",
            "password": "Employee@456"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2027-03-02",
            "end_date": "2027-03-02",
            "reason": "Cross-team WFH access test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    wfh_id = create_response.json()["id"]

    # Priya tries to approve the other team's WFH request
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    approval_response = client.post(
        f"/manager/wfh/{wfh_id}/approve",
        json={},
        headers=manager_headers
    )

    assert approval_response.status_code == 403

def test_manager_cannot_view_other_teams_requests(client, seed_users, db_session):
    # Create a second manager
    second_manager = User(
        name="Second Manager",
        email="second.manager@leavedesk.test",
        hashed_password=get_password_hash("Manager@456"),
        role="manager",
        manager_id=None
    )
    db_session.add(second_manager)
    db_session.flush()

    # Create an employee under the second manager
    second_employee = User(
        name="Other Team Employee",
        email="other.employee@leavedesk.test",
        hashed_password=get_password_hash("Employee@456"),
        role="employee",
        manager_id=second_manager.id
    )
    db_session.add(second_employee)
    db_session.commit()

    # Other employee creates a leave request
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "other.employee@leavedesk.test",
            "password": "Employee@456"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2027-03-05",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "Cross-team viewing test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201

    # Priya tries to view the other team's requests
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    response = client.get(
        "/manager/requests",
        params={"employee_id": second_employee.id},
        headers=manager_headers
    )

    assert response.status_code == 403

def test_employee_can_download_leave_csv_report(client, seed_users):
    # Arjun logs in
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    # Create a leave request
    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-10-15",
            "leave_type": "CASUAL",
            "duration_type": "FULL_DAY",
            "reason": "CSV report test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201

    # Download the CSV report
    response = client.get(
        "/reports/leaves",
        headers=employee_headers
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "leave_report_arjun" in response.headers["content-disposition"]
    assert "date,request_type,leave_type,duration_type,half,hours,days_counted,status,reason,decided_by,decided_at" in response.text
    assert "CSV report test" in response.text

def test_employee_csv_report_contains_summary(client, seed_users):
    # Arjun logs in
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    # Create a leave request
    create_response = client.post(
        "/leaves",
        json={
            "leave_date": "2026-10-16",
            "leave_type": "SICK",
            "duration_type": "FULL_DAY",
            "reason": "CSV summary test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    leave_id = create_response.json()["id"]

    # Approve the leave so it contributes to approved totals
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    approval_response = client.post(
        f"/manager/leaves/{leave_id}/approve",
        json={},
        headers=manager_headers
    )
    assert approval_response.status_code == 200

    # Download the report
    response = client.get(
        "/reports/leaves",
        headers=employee_headers
    )

    assert response.status_code == 200
    assert "CSV summary test" in response.text
    assert "1.00" in response.text
    assert "APPROVED" in response.text

def test_employee_csv_report_includes_wfh_working_days(client, seed_users):
    # Arjun logs in
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    # Create a two-working-day WFH request (Monday and Tuesday)
    create_response = client.post(
        "/wfh",
        json={
            "start_date": "2026-11-23",
            "end_date": "2026-11-24",
            "reason": "CSV WFH report test"
        },
        headers=employee_headers
    )
    assert create_response.status_code == 201
    wfh_id = create_response.json()["id"]

    # Manager approves the WFH request
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_headers = {
        "Authorization": f"Bearer {manager_login.json()['access_token']}"
    }

    approval_response = client.post(
        f"/manager/wfh/{wfh_id}/approve",
        json={},
        headers=manager_headers
    )
    assert approval_response.status_code == 200

    # Download the CSV report
    response = client.get(
        "/reports/leaves",
        headers=employee_headers
    )

    assert response.status_code == 200
    assert "2026-11-23,WFH" in response.text
    assert "2026-11-24,WFH" in response.text
    assert response.text.count("WFH") >= 2

def test_employee_csv_report_when_no_requests(client, seed_users):
    # Arjun logs in but creates no leave or WFH requests
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }

    # Download the empty report
    response = client.get(
        "/reports/leaves",
        headers=employee_headers
    )

    assert response.status_code == 200

    expected_header = (
        "date,request_type,leave_type,duration_type,half,hours,"
        "days_counted,status,reason,decided_by,decided_at"
    )
    assert expected_header in response.text

    # Empty report should still contain zero-valued summary totals
    assert "0.00" in response.text
    assert "Pending requests,0" in response.text
    assert "Rejected requests,0" in response.text
def test_manager_can_download_direct_report_csv(client, seed_users):
    # Login as manager
    manager_login = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    manager_user = client.get("/auth/me")

    manager_token = manager_login.json()["access_token"]
   
    # Get Arjun's user ID
    employee_login = client.post(
        "/auth/login",
        json={
            "email": "arjun@leavedesk.test",
            "password": "Employee@123"
        }
    )
    employee_token = employee_login.json()["access_token"]

    employee_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {employee_token}"}
    )
    employee_id = employee_response.json()["id"]

    # Manager downloads Arjun's report
    response = client.get(
        f"/reports/leaves?employee_id={employee_id}",
        headers={"Authorization": f"Bearer {manager_token}"}
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
def test_manager_cannot_download_other_teams_csv(client, seed_users, db_session):
    from app.models.user import User

    # Create another manager
    other_manager = User(
        name="Other Manager",
        email="other.manager@leavedesk.test",
        hashed_password=get_password_hash("Other@123"),
        role="manager",
        manager_id=None
    )
    db_session.add(other_manager)
    db_session.flush()

    # Create an employee under the other manager
    other_employee = User(
        name="Other Employee",
        email="other.employee@leavedesk.test",
        hashed_password=get_password_hash("Employee@123"),
        role="employee",
        manager_id=other_manager.id
    )
    db_session.add(other_employee)
    db_session.commit()

    # Login as Priya
    login_response = client.post(
        "/auth/login",
        json={
            "email": "priya.manager@leavedesk.test",
            "password": "Manager@123"
        }
    )
    token = login_response.json()["access_token"]

    # Request another manager's employee report
    response = client.get(
        f"/reports/leaves?employee_id={other_employee.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}