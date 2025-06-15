from typing import Any

from pydantic import BaseModel as PydanticBaseModel
from pydantic import field_validator


class BaseModel(PydanticBaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def empty_string_to_none(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    model_config = {
        "str_strip_whitespace": True,
        "extra": "forbid",
        "validate_assignment": True,
        "populate_by_name": True,
    }
