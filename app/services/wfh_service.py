from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.leave import LeaveRequest
from app.models.wfh import WFHRequest
def count_working_days(start_date: date, end_date: date) -> int:
    """Count weekdays (Monday to Friday) in an inclusive date range."""
    total = 0
    current_date = start_date

    while current_date <= end_date:
        if current_date.weekday() < 5:
            total += 1

        current_date += timedelta(days=1)

    return total


def find_wfh_conflict(
    db: Session,
    employee_id: int,
    start_date: date,
    end_date: date,
) -> bool:
    """Check for overlapping active WFH or full-day leave requests."""

    # Check overlapping pending or approved WFH requests.
    existing_wfh = db.scalars(
        select(WFHRequest).where(
            WFHRequest.employee_id == employee_id,
            WFHRequest.status.in_(["PENDING", "APPROVED"]),
            WFHRequest.start_date <= end_date,
            WFHRequest.end_date >= start_date,
        )
    ).first()

    if existing_wfh:
        return True

    # Check full-day pending or approved leave on working days.
    existing_leaves = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_(["PENDING", "APPROVED"]),
            LeaveRequest.duration_type == "FULL_DAY",
            LeaveRequest.leave_date >= start_date,
            LeaveRequest.leave_date <= end_date,
        )
    ).all()

    for leave in existing_leaves:
        if leave.leave_date.weekday() < 5:
            return True

    return False