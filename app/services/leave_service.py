
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.leave import LeaveRequest
from app.models.wfh import WFHRequest
from app.schemas.leave import LeaveCreate


def calculate_days_counted(leave: LeaveCreate) -> Decimal:
    """Calculate leave duration in days."""

    if leave.duration_type == "FULL_DAY":
        return Decimal("1.00")

    if leave.duration_type == "HALF_DAY":
        return Decimal("0.50")

    assert leave.hours is not None
    return Decimal(leave.hours) / Decimal("8")


def find_leave_conflict(
    db: Session,
    employee_id: int,
    leave: LeaveCreate,
) -> bool:
    """Check whether an active leave or WFH request conflicts."""

    existing_requests = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.leave_date == leave.leave_date,
            LeaveRequest.status.in_(["PENDING", "APPROVED"]),
        )
    ).all()

    for existing in existing_requests:
        if (
            leave.duration_type == "FULL_DAY"
            or existing.duration_type == "FULL_DAY"
        ):
            return True

        if (
            leave.duration_type == "HALF_DAY"
            and existing.duration_type == "HALF_DAY"
        ):
            if leave.half == existing.half:
                return True

        # Conservative assumption: only one active HOURS request per date.
        if (
            leave.duration_type == "HOURS"
            or existing.duration_type == "HOURS"
        ):
            return True

    # Prevent a full-day leave from overlapping an active WFH request.
    if leave.duration_type == "FULL_DAY":
        existing_wfh = db.scalars(
            select(WFHRequest).where(
                WFHRequest.employee_id == employee_id,
                WFHRequest.status.in_(["PENDING", "APPROVED"]),
                WFHRequest.start_date <= leave.leave_date,
                WFHRequest.end_date >= leave.leave_date,
            )
        ).first()

        if existing_wfh is not None:
            return True

    return False