import datetime

from typing import Self

from pydantic import model_validator

from .base import BaseModel


class TimeRange(BaseModel):
    start: datetime.datetime
    end: datetime.datetime

    @model_validator(mode="after")
    def end_after_start(self) -> Self:
        if self.start > self.end:
            raise ValueError("End must be after start")
        return self
