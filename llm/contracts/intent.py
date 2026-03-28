from pydantic import BaseModel, Field
from typing import List, Literal


class Intent(BaseModel):
    intent_summary: str = Field(
        description="Short normalized summary of the user request."
    )
    question_type: Literal[
        "summary",
        "extreme",
        "temporal_change",
        "count",
        "comparison",
        "unknown",
    ] = Field(description="High-level semantic task family.")
    data_domain: Literal[
        "lab",
        "medication",
        "diagnosis",
        "procedure",
        "other",
    ] = Field(description="Primary clinical/analytic domain referenced.")
    lab_name: str = Field(
        description="Primary target measure/entity."
    )
    time_scope: Literal[
        "icu_period",
        "hospital_period",
        "before_icu",
        "after_icu",
        "unspecified",
    ] = Field(description="Temporal focus implied by the request.")
    result_scope: Literal[
        "icu_stay",
        "patient",
        "cohort",
        "unspecified",
    ] = Field(description="Unit/population focus requested.")
    details: List[str] = Field(
        default_factory=list,
        description="Additional request details.",
    )
    notes: str = Field(
        description="Additional normalized context for downstream modules."
    )
