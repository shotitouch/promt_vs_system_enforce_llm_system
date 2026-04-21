from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


ArtifactKind = Literal["table", "grouped_table", "scalar"]


class StepBase(BaseModel):
    step_id: str = Field(description="Unique identifier for this reduction step.")
    input_artifact: str = Field(
        description="Name of the input artifact consumed by this step."
    )
    output_artifact: str = Field(
        description="Name of the artifact produced by this step."
    )

    model_config = {"extra": "forbid"}


class GroupByStep(StepBase):
    op: Literal["group_by"]
    keys: List[str]


class SortByStep(StepBase):
    op: Literal["sort_by"]
    by: List[str]
    ascending: bool = True


class SelectColumnsStep(StepBase):
    op: Literal["select_columns"]
    columns: List[str]


class RenameColumnsStep(StepBase):
    op: Literal["rename_columns"]
    rename_map: dict[str, str]


class TakeFirstStep(StepBase):
    op: Literal["take_first"]
    count: int = 1

    @model_validator(mode="after")
    def validate_count(self):
        if self.count < 1:
            raise ValueError("count must be >= 1")
        return self


class TakeLastStep(StepBase):
    op: Literal["take_last"]
    count: int = 1

    @model_validator(mode="after")
    def validate_count(self):
        if self.count < 1:
            raise ValueError("count must be >= 1")
        return self


class TakeMinStep(StepBase):
    op: Literal["take_min"]
    by_column: str
    count: int = 1

    @model_validator(mode="after")
    def validate_count(self):
        if self.count < 1:
            raise ValueError("count must be >= 1")
        return self


class TakeMaxStep(StepBase):
    op: Literal["take_max"]
    by_column: str
    count: int = 1

    @model_validator(mode="after")
    def validate_count(self):
        if self.count < 1:
            raise ValueError("count must be >= 1")
        return self


class MergeOnKeysStep(BaseModel):
    op: Literal["merge_on_keys"]
    step_id: str = Field(description="Unique identifier for this reduction step.")
    left_artifact: str
    right_artifact: str
    output_artifact: str
    keys: List[str]

    model_config = {"extra": "forbid"}


class SubtractStep(StepBase):
    op: Literal["subtract"]
    left_column: str
    right_column: str
    output_column: str


class AddStep(StepBase):
    op: Literal["add"]
    left_column: str
    right_column: str
    output_column: str


class MultiplyStep(StepBase):
    op: Literal["multiply"]
    left_column: str
    right_column: str
    output_column: str


class DivideStep(StepBase):
    op: Literal["divide"]
    numerator_column: str
    denominator_column: str
    output_column: str


class AbsStep(StepBase):
    op: Literal["abs"]
    source_column: str
    output_column: str


class CompareStep(StepBase):
    op: Literal["compare"]
    left_column: str
    right_column: str
    comparator: Literal["gt", "lt", "eq", "gte", "lte"]
    output_column: str


class AggregateStatStep(StepBase):
    op: Literal["aggregate_stat"]
    source_column: Optional[str] = None
    statistic: Literal["mean", "median", "min", "max", "percentile", "count"]
    percentile: Optional[float] = None
    output_column: str

    @model_validator(mode="after")
    def validate_percentile(self):
        if self.statistic == "percentile":
            if self.percentile is None:
                raise ValueError("percentile is required when statistic='percentile'")
        elif self.percentile is not None:
            raise ValueError("percentile must be omitted unless statistic='percentile'")
        return self


class ProportionTrueStep(StepBase):
    op: Literal["proportion_true"]
    source_column: str
    output_column: str


ReductionStep = Annotated[
    Union[
        GroupByStep,
        SortByStep,
        SelectColumnsStep,
        RenameColumnsStep,
        TakeFirstStep,
        TakeLastStep,
        TakeMinStep,
        TakeMaxStep,
        MergeOnKeysStep,
        SubtractStep,
        AddStep,
        MultiplyStep,
        DivideStep,
        AbsStep,
        CompareStep,
        AggregateStatStep,
        ProportionTrueStep,
    ],
    Field(discriminator="op"),
]


class ReductionPlan(BaseModel):
    status: Literal["supported", "unsupported", "no_reduction_needed"] = Field(
        description="Whether the requested reduction can be safely expressed using the supported primitive operations."
    )
    reason: str = Field(
        description="Short explanation of why the plan is supported or unsupported."
    )
    final_artifact: Optional[str] = Field(
        default=None,
        description="Name of the final artifact returned by the plan. Required when status='supported'.",
    )
    final_kind: Optional[ArtifactKind] = Field(
        default=None,
        description="Kind of the final artifact. Required when status='supported'.",
    )
    steps: List[ReductionStep] = Field(
        default_factory=list,
        description="Ordered list of reduction steps. Must be empty when status='unsupported'.",
    )

    @model_validator(mode="after")
    def validate_plan(self):
        if self.status == "unsupported":
            if self.steps:
                raise ValueError("steps must be empty when status='unsupported'")
            return self
        if self.status == "no_reduction_needed":
            if not self.final_artifact:
                raise ValueError(
                    "final_artifact is required when status='no_reduction_needed'"
                )
            if not self.final_kind:
                raise ValueError(
                    "final_kind is required when status='no_reduction_needed'"
                )
            if self.steps:
                raise ValueError(
                    "steps must be empty when status='no_reduction_needed'"
                )
            return self
        if not self.final_artifact:
            raise ValueError("final_artifact is required when status='supported'")
        if not self.final_kind:
            raise ValueError("final_kind is required when status='supported'")
        if not self.steps:
            raise ValueError("steps are required when status='supported'")
        return self

    model_config = {"extra": "forbid"}
