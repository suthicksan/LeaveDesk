from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.dependencies import get_db
from app.models.leave import LeaveRequest
from app.models.user import User
from app.schemas.leave import LeaveCreate, LeaveResponse
from datetime import date
from sqlalchemy import select
from app.services.leave_service import (
    calculate_days_counted,
    find_leave_conflict,
)

router = APIRouter(prefix="/leaves", tags=["Leave Requests"])


@router.post(
    "",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_leave(
    leave_data: LeaveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conflict = find_leave_conflict(
        db=db,
        employee_id=current_user.id,
        leave=leave_data,
    )

    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active leave or WFH request conflicts with this date",
        )

    leave_request = LeaveRequest(
        employee_id=current_user.id,
        leave_date=leave_data.leave_date,
        leave_type=leave_data.leave_type,
        duration_type=leave_data.duration_type,
        half=leave_data.half,
        hours=leave_data.hours,
        days_counted=calculate_days_counted(leave_data),
        reason=leave_data.reason,
        status="PENDING",
    )

    db.add(leave_request)
    db.commit()
    db.refresh(leave_request)

    return leave_request


@router.get("/me", response_model=list[LeaveResponse])
def get_my_leaves(
    status_filter: str | None = Query(default=None, alias="status"),
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(LeaveRequest).where(
        LeaveRequest.employee_id == current_user.id
    )

    if status_filter:
        query = query.where(
            LeaveRequest.status == status_filter.upper()
        )

    if from_date:
        query = query.where(
            LeaveRequest.leave_date >= from_date
        )

    if to_date:
        query = query.where(
            LeaveRequest.leave_date <= to_date
        )

    query = query.order_by(LeaveRequest.created_at.desc())

    return db.scalars(query).all()

@router.post("/{leave_id}/cancel")
def cancel_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    leave_request = db.get(LeaveRequest, leave_id)

    # Do not reveal another employee's request.
    if (
        leave_request is None
        or leave_request.employee_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found",
        )

    if leave_request.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending leave requests can be cancelled",
        )

    leave_request.status = "CANCELLED"
    db.commit()

    return {"message": "Leave request cancelled successfully"}
