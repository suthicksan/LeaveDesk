from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.leave import LeaveCreate


def test_full_day_leave():
    request = LeaveCreate(
        leave_date=date(2026, 11, 20),
        leave_type="CASUAL",
        duration_type="FULL_DAY"
    )

    assert request.duration_type == "FULL_DAY"
    assert request.half is None
    assert request.hours is None


def test_half_day_leave():
    request = LeaveCreate(
        leave_date=date(2026, 11, 20),
        leave_type="SICK",
        duration_type="HALF_DAY",
        half="FIRST_HALF"
    )

    assert request.duration_type == "HALF_DAY"
    assert request.half == "FIRST_HALF"


def test_hours_leave():
    request = LeaveCreate(
        leave_date=date(2026, 11, 20),
        leave_type="EARNED",
        duration_type="HOURS",
        hours=2
    )

    assert request.duration_type == "HOURS"
    assert request.hours == 2


@pytest.mark.parametrize("payload", [
    {
        "duration_type": "FULL_DAY",
        "half": "FIRST_HALF"
    },
    {
        "duration_type": "FULL_DAY",
        "hours": 2
    },
    {
        "duration_type": "HALF_DAY"
    },
    {
        "duration_type": "HALF_DAY",
        "half": "FIRST_HALF",
        "hours": 2
    },
    {
        "duration_type": "HOURS"
    },
    {
        "duration_type": "HOURS",
        "hours": 2,
        "half": "SECOND_HALF"
    },
])
def test_invalid_duration_combinations(payload):
    data = {
        "leave_date": date(2026, 11, 20),
        "leave_type": "CASUAL",
        **payload
    }

    with pytest.raises(ValidationError):
        LeaveCreate(**data)


@pytest.mark.parametrize("hours", [0, 4, -1])
def test_invalid_hours(hours):
    with pytest.raises(ValidationError):
        LeaveCreate(
            leave_date=date(2026, 11, 20),
            leave_type="CASUAL",
            duration_type="HOURS",
            hours=hours
        )


def test_invalid_leave_type():
    with pytest.raises(ValidationError):
        LeaveCreate(
            leave_date=date(2026, 11, 20),
            leave_type="UNPAID",
            duration_type="FULL_DAY"
        )