from decimal import Decimal

from app.schemas.leave import LeaveCreate


def calculate_days_counted(leave: LeaveCreate) -> Decimal:
    """Calculate the leave duration in days."""

    if leave.duration_type == "FULL_DAY":
        return Decimal("1.00")

    if leave.duration_type == "HALF_DAY":
        return Decimal("0.50")

    # HOURS: convert working hours into an 8-hour workday.
    assert leave.hours is not None
    return Decimal(leave.hours) / Decimal("8")