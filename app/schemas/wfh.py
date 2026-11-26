from datetime import date, datetime, timedelta
from pydantic import BaseModel, ConfigDict, Field, model_validator
class WFHCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")

        working_days = sum(
            1
            for day_number in range(
                (self.end_date - self.start_date).days + 1
            )
            if (
                self.start_date + timedelta(days=day_number)
            ).weekday() < 5
        )

        if working_days == 0:
            raise ValueError("WFH request must include at least one working day")

        if working_days > 2:
            raise ValueError("WFH request cannot exceed 2 working days")

        return self


class WFHResponse(BaseModel):
    id: int
    employee_id: int
    start_date: date
    end_date: date
    reason: str | None
    status: str
    created_at: datetime

    # Manager decision details
    decided_by: int | None = None
    decided_at: datetime | None = None
    decision_comment: str | None = None

    model_config = ConfigDict(from_attributes=True)