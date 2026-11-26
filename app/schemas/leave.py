from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from decimal import Decimal
from pydantic import ConfigDict
class LeaveResponse(BaseModel):
    id: int
    employee_id: int
    leave_date: date
    leave_type: str
    duration_type: str
    half: str | None
    hours: int | None
    days_counted: Decimal
    reason: str | None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
class LeaveCreate(BaseModel):

    # Date for which leave is requested
    leave_date: date

    # Permitted leave categories
    leave_type: Literal["CASUAL", "SICK", "EARNED"]

    # Permitted duration types
    duration_type: Literal["FULL_DAY", "HALF_DAY", "HOURS"]

    # Required only for HALF_DAY
    half: Literal["FIRST_HALF", "SECOND_HALF"] | None = None

    # Required only for HOURS; minimum 1, maximum 3
    hours: int | None = Field(default=None, ge=1, le=3)

    # Optional reason
    reason: str | None = None

    @model_validator(mode="after")
    def validate_duration(self):

        if self.duration_type == "FULL_DAY":
            if self.half is not None or self.hours is not None:
                raise ValueError(
                    "FULL_DAY must not include half or hours"
                )

        elif self.duration_type == "HALF_DAY":
            if self.half is None:
                raise ValueError(
                    "HALF_DAY requires FIRST_HALF or SECOND_HALF"
                )

            if self.hours is not None:
                raise ValueError(
                    "HALF_DAY must not include hours"
                )

        elif self.duration_type == "HOURS":
            if self.hours is None:
                raise ValueError(
                    "HOURS requires a value between 1 and 3"
                )

            if self.half is not None:
                raise ValueError(
                    "HOURS must not include half"
                )

        return self