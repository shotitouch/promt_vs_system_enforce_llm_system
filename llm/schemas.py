# llm/schemas.py
from pydantic import BaseModel, Field
from typing import Literal

class Mode2Intent(BaseModel):
    """
    Structured analytical intent for Mode 2.
    Supports arbitrary lab metrics at the schema level.
    """

    metric: str = Field(
        description=(
            "Name of the laboratory test to analyze "
            "(e.g., creatinine, sodium, potassium)."
        )
    )

    time_window: Literal["icu", "other"] = Field(
        description=(
            "Time window over which the analysis is performed."
            "'icu' is recognized. "
             "Use 'other' if the request does not match a supported window."
            )
    )

    operation: Literal["summary"] = Field(
        description="Aggregate summary over the selected lab values."
    )
