from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class PolicyDecision(BaseModel):
    decision: Literal["allow", "refuse"] = Field(
        description="Whether the request should proceed."
    )
    reason: str = Field(
        description="Short explanation for the decision."
    )
    scope_category: Literal["in_scope", "out_of_scope", "unknown"] = Field(
        description="Normalized scope judgment."
    )
    violations: List[str] = Field(
        default_factory=list,
        description="Explicit normalized rule violations.",
    )
    unsafe_request: Optional[bool] = Field(
        default=None,
        description="Whether the request attempts to bypass or undermine system constraints.",
    )

    class Config:
        extra = "forbid"
