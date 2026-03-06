from pydantic import BaseModel, Field
from typing import List, Literal


class Mode3Intent(BaseModel):
    intent_summary: str = Field(
        description="Short normalized summary of the user request."
    )
    task_kind: Literal[
        "summary",
        "extreme",
        "temporal_change",
        "count",
        "comparison",
        "unknown",
    ] = Field(description="High-level semantic task family.")
    subject_domain: Literal[
        "lab",
        "medication",
        "diagnosis",
        "procedure",
        "other",
    ] = Field(description="Primary clinical/analytic domain referenced.")
    measure_name: str = Field(
        description="Primary target measure/entity."
    )
    temporal_focus: Literal[
        "icu_period",
        "hospital_period",
        "before_icu",
        "after_icu",
        "unspecified",
    ] = Field(description="Temporal focus implied by the request.")
    subject_focus: Literal[
        "icu_stay",
        "patient",
        "cohort",
        "unspecified",
    ] = Field(description="Unit/population focus requested.")
    qualifiers: List[str] = Field(
        default_factory=list,
        description="Additional semantic qualifiers.",
    )
    intent_notes: str = Field(
        description="Additional normalized context for downstream modules."
    )

