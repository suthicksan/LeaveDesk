from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LeaveRequest(Base):

    __tablename__ = "leave_requests"

    # Unique leave request ID
    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    # Employee who applied for leave
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Date for which leave is requested
    leave_date: Mapped[datetime.date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )

    # CASUAL, SICK or EARNED
    leave_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    # FULL_DAY, HALF_DAY or HOURS
    duration_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    # FIRST_HALF or SECOND_HALF
    half: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    # Number of hours, between 1 and 3
    hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    # Calculated leave duration
    days_counted: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False
    )

    # Optional reason for leave
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # PENDING, APPROVED, REJECTED or CANCELLED
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False,
        index=True
    )

    # Request creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Manager who approved or rejected the request
    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    # Manager decision timestamp
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Optional manager decision comment
    decision_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
