from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, require_role
from app.db.dependencies import get_db
from app.models.user import User
from app.models.leave import LeaveRequest
from app.models.wfh import WFHRequest
from app.schemas.manager import DecisionRequest

router = APIRouter(
    prefix="/manager",
    tags=["Manager"]
)

get_current_manager = require_role("manager")



@router.get("/requests")
def get_team_requests(
    status_filter: str = Query(default="PENDING", alias="status"),
    employee_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    # Get direct reports
    team_query = select(User.id).where(
        User.manager_id == current_user.id
    )

    team_member_ids = db.scalars(team_query).all()

    if employee_id is not None and employee_id not in team_member_ids:
        raise HTTPException(
            status_code=403,
            detail="Not authorized for this employee"
        )

    # Common filters
    leave_query = select(LeaveRequest).where(
        LeaveRequest.employee_id.in_(team_member_ids)
    )

    wfh_query = select(WFHRequest).where(
        WFHRequest.employee_id.in_(team_member_ids)
    )

    if status_filter:
      status_value = status_filter.upper()

      leave_query = leave_query.where(
        LeaveRequest.status == status_value
    )
      wfh_query = wfh_query.where(
        WFHRequest.status == status_value
    )

    if employee_id is not None:
        leave_query = leave_query.where(
            LeaveRequest.employee_id == employee_id
        )
        wfh_query = wfh_query.where(
            WFHRequest.employee_id == employee_id
        )

    if from_date:
        leave_query = leave_query.where(
            LeaveRequest.leave_date >= from_date
        )
        wfh_query = wfh_query.where(
            WFHRequest.end_date >= from_date
        )

    if to_date:
        leave_query = leave_query.where(
            LeaveRequest.leave_date <= to_date
        )
        wfh_query = wfh_query.where(
            WFHRequest.start_date <= to_date
        )

    # Fetch both types of requests
    leave_requests = db.scalars(leave_query).all()
    wfh_requests = db.scalars(wfh_query).all()

    # Combine results with request type labels
    results = []

    for leave in leave_requests:
        results.append({
            "request_type": "LEAVE",
            "id": leave.id,
            "employee_id": leave.employee_id,
            "leave_date": leave.leave_date,
            "leave_type": leave.leave_type,
            "duration_type": leave.duration_type,
            "half": leave.half,
            "hours": leave.hours,
            "days_counted": leave.days_counted,
            "reason": leave.reason,
            "status": leave.status,
            "created_at": leave.created_at,
            "decided_by": leave.decided_by,
            "decided_at": leave.decided_at,
            "decision_comment": leave.decision_comment
        })

    for wfh in wfh_requests:
        results.append({
            "request_type": "WFH",
            "id": wfh.id,
            "employee_id": wfh.employee_id,
            "start_date": wfh.start_date,
            "end_date": wfh.end_date,
            "reason": wfh.reason,
            "status": wfh.status,
            "created_at": wfh.created_at,
            "decided_by": wfh.decided_by,
            "decided_at": wfh.decided_at,
            "decision_comment": wfh.decision_comment
        })

    # Newest requests first
    results.sort(
        key=lambda request: request["created_at"],
        reverse=True
    )

    return results
@router.post("/leaves/{leave_id}/approve")
def approve_leave(
    leave_id: int,
    decision: DecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    leave = db.get(LeaveRequest, leave_id)

    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    employee = db.get(User, leave.employee_id)

    if not employee or employee.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this employee")

    if leave.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending requests can be approved")

    leave.status = "APPROVED"
    leave.decided_by = current_user.id
    leave.decided_at = datetime.now(timezone.utc)
    leave.decision_comment = decision.comment

    db.commit()
    db.refresh(leave)

    return {"message": "Leave request approved", "leave_id": leave.id}


@router.post("/leaves/{leave_id}/reject")
def reject_leave(
    leave_id: int,
    decision: DecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    leave = db.get(LeaveRequest, leave_id)

    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    employee = db.get(User, leave.employee_id)

    if not employee or employee.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this employee")

    if leave.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending requests can be rejected")

    if not decision.comment or len(decision.comment.strip()) < 5:
        raise HTTPException(status_code=422, detail="Rejection comment must contain at least 5 characters")

    leave.status = "REJECTED"
    leave.decided_by = current_user.id
    leave.decided_at = datetime.now(timezone.utc)
    leave.decision_comment = decision.comment

    db.commit()
    db.refresh(leave)

    return {"message": "Leave request rejected", "leave_id": leave.id}


@router.post("/wfh/{wfh_id}/approve")
def approve_wfh(
    wfh_id: int,
    decision: DecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    wfh = db.get(WFHRequest, wfh_id)

    if not wfh:
        raise HTTPException(status_code=404, detail="WFH request not found")

    employee = db.get(User, wfh.employee_id)

    if not employee or employee.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this employee")

    if wfh.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending requests can be approved")

    wfh.status = "APPROVED"
    wfh.decided_by = current_user.id
    wfh.decided_at = datetime.now(timezone.utc)
    wfh.decision_comment = decision.comment

    db.commit()
    db.refresh(wfh)

    return {"message": "WFH request approved", "wfh_id": wfh.id}


@router.post("/wfh/{wfh_id}/reject")
def reject_wfh(
    wfh_id: int,
    decision: DecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    wfh = db.get(WFHRequest, wfh_id)

    if not wfh:
        raise HTTPException(status_code=404, detail="WFH request not found")

    employee = db.get(User, wfh.employee_id)

    if not employee or employee.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this employee")

    if wfh.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending requests can be rejected")

    if not decision.comment or len(decision.comment.strip()) < 5:
        raise HTTPException(status_code=422, detail="Rejection comment must contain at least 5 characters")

    wfh.status = "REJECTED"
    wfh.decided_by = current_user.id
    wfh.decided_at = datetime.now(timezone.utc)
    wfh.decision_comment = decision.comment

    db.commit()
    db.refresh(wfh)

    return {"message": "WFH request rejected", "wfh_id": wfh.id}