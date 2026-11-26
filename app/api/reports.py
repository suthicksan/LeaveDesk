import csv
from datetime import date
from io import StringIO

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.dependencies import get_db
from app.models.user import User
from app.models.leave import LeaveRequest
from app.models.wfh import WFHRequest


router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)


def count_working_days(start_date: date, end_date: date) -> int:
    total = 0
    current = start_date

    while current <= end_date:
        if current.weekday() < 5:
            total += 1

        current = current.replace(day=current.day) + relativedelta(days=1)

    return total


@router.get("/leaves")
def download_leave_report(
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    today = date.today()
    from_date = today - relativedelta(months=6)
    to_date = today

    # Decide whose report can be downloaded
    if current_user.role == "manager":
        if employee_id is None:
            raise HTTPException(
                status_code=400,
                detail="Managers must provide an employee_id"
            )

        employee = db.get(User, employee_id)

        if not employee or employee.manager_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized for this employee"
            )

        report_user = employee

    else:
        if employee_id is not None and employee_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only download your own report"
            )

        report_user = current_user

    # Fetch leave requests in the report period
    leave_requests = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == report_user.id,
            LeaveRequest.leave_date >= from_date,
            LeaveRequest.leave_date <= to_date
        )
    ).all()

    # Fetch WFH requests overlapping the report period
    wfh_requests = db.scalars(
        select(WFHRequest).where(
            WFHRequest.employee_id == report_user.id,
            WFHRequest.start_date <= to_date,
            WFHRequest.end_date >= from_date
        )
    ).all()

    output = StringIO()
    writer = csv.writer(output)

    # Exact required CSV header
    writer.writerow([
        "date",
        "request_type",
        "leave_type",
        "duration_type",
        "half",
        "hours",
        "days_counted",
        "status",
        "reason",
        "decided_by",
        "decided_at"
    ])

    rows = []

    # Add leave request rows
    for leave in leave_requests:
        rows.append((
            leave.leave_date,
            [
                leave.leave_date.isoformat(),
                "LEAVE",
                leave.leave_type,
                leave.duration_type,
                leave.half or "",
                leave.hours if leave.hours is not None else "",
                f"{float(leave.days_counted):.2f}",
                leave.status,
                leave.reason or "",
                leave.decided_by or "",
                leave.decided_at.isoformat() if leave.decided_at else ""
            ]
        ))

    # Add one WFH row per working day
    for wfh in wfh_requests:
        current = max(wfh.start_date, from_date)
        last_day = min(wfh.end_date, to_date)

        while current <= last_day:
            if current.weekday() < 5:
                rows.append((
                    current,
                    [
                        current.isoformat(),
                        "WFH",
                        "",
                        "",
                        "",
                        "",
                        "1.00",
                        wfh.status,
                        wfh.reason or "",
                        wfh.decided_by or "",
                        wfh.decided_at.isoformat() if wfh.decided_at else ""
                    ]
                ))

            current += relativedelta(days=1)

    # Sort records oldest first
    rows.sort(key=lambda item: item[0])

    for _, row in rows:
        writer.writerow(row)

    # Calculate summary totals
    approved_leave_days = sum(
        float(leave.days_counted)
        for leave in leave_requests
        if leave.status == "APPROVED"
    )

    approved_wfh_days = sum(
        count_working_days(
            max(wfh.start_date, from_date),
            min(wfh.end_date, to_date)
        )
        for wfh in wfh_requests
        if wfh.status == "APPROVED"
    )

    pending_count = (
        sum(1 for leave in leave_requests if leave.status == "PENDING")
        + sum(1 for wfh in wfh_requests if wfh.status == "PENDING")
    )

    rejected_count = (
        sum(1 for leave in leave_requests if leave.status == "REJECTED")
        + sum(1 for wfh in wfh_requests if wfh.status == "REJECTED")
    )

    # Add summary after a blank line
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Approved leave days", f"{approved_leave_days:.2f}"])
    writer.writerow(["Approved WFH days", approved_wfh_days])
    writer.writerow(["Pending requests", pending_count])
    writer.writerow(["Rejected requests", rejected_count])

    filename = (
        f"leave_report_{report_user.email}_"
        f"{from_date.isoformat()}_{to_date.isoformat()}.csv"
    )

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )