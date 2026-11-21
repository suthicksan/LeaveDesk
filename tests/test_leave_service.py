
from datetime import date
from decimal import Decimal

import pytest

from app.schemas.leave import LeaveCreate
from app.services.leave_service import calculate_days_counted


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {
                "leave_date": date(2026, 11, 23),
                "leave_type": "CASUAL",
                "duration_type": "FULL_DAY",
            },
            Decimal("1.00"),
        ),
        (
            {
                "leave_date": date(2026, 11, 23),
                "leave_type": "SICK",
                "duration_type": "HALF_DAY",
                "half": "FIRST_HALF",
            },
            Decimal("0.50"),
        ),
        (
            {
                "leave_date": date(2026, 11, 23),
                "leave_type": "EARNED",
                "duration_type": "HOURS",
                "hours": 2,
            },
            Decimal("0.25"),
        ),
        (
            {
                "leave_date": date(2026, 11, 23),
                "leave_type": "CASUAL",
                "duration_type": "HOURS",
                "hours": 3,
            },
            Decimal("0.375"),
        ),
    ],
)
def test_calculate_days_counted(payload, expected):
    leave = LeaveCreate(**payload)
    assert calculate_days_counted(leave) == expected
