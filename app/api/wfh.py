from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.dependencies import get_db
from app.models.user import User
from app.models.wfh import WFHRequest
from app.schemas.wfh import WFHCreate, WFHResponse
from app.services.wfh_service import find_wfh_conflict

router = APIRouter(prefix="/wfh", tags=["Work From Home"])


@router.post("", response_model=WFHResponse, status_code=201)
def create_wfh(
    wfh_data: WFHCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conflict = find_wfh_conflict(
        db,
        current_user.id,
        wfh_data.start_date,
        wfh_data.end_date,
    )

    if conflict:
        raise HTTPException(
            status_code=409,
            detail="WFH request conflicts with an existing active request",
        )

    wfh_request = WFHRequest(
        employee_id=current_user.id,
        start_date=wfh_data.start_date,
        end_date=wfh_data.end_date,
        reason=wfh_data.reason,
        status="PENDING",
    )

    db.add(wfh_request)
    db.commit()
    db.refresh(wfh_request)

    return wfh_request


@router.get("/me", response_model=list[WFHResponse])
def get_my_wfh_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(WFHRequest).where(
        WFHRequest.employee_id == current_user.id
    )

    if status_filter:
        query = query.where(
            WFHRequest.status == status_filter.upper()
        )

    if from_date:
        query = query.where(
            WFHRequest.end_date >= from_date
        )

    if to_date:
        query = query.where(
            WFHRequest.start_date <= to_date
        )

    query = query.order_by(WFHRequest.created_at.desc())

    return db.scalars(query).all()



@router.post("/{wfh_id}/cancel")
def cancel_wfh(
    wfh_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wfh_request = db.get(WFHRequest, wfh_id)

    if wfh_request is None or wfh_request.employee_id != current_user.id:
        raise HTTPException(status_code=404, detail="WFH request not found")

    if wfh_request.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Only pending WFH requests can be cancelled",
        )

    wfh_request.status = "CANCELLED"
    db.commit()

    return {"message": "WFH request cancelled successfully"}
