from datetime import datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
class WFHRequest(Base):
    __tablename__ = "wfh_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    decision_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )