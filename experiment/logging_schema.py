from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


# ============================================================
# Controlled vocab
# ============================================================

SQLStage = Literal["discovery", "final", "template"]

LLMStage = Literal[
    "intent",
    "discovery",
    "final",
    "validation",
    "policy",
    "aggregation",
    "expression",
    "other",
]

FailureStage = Literal[
    "discovery",
    "compile",
    "sql_gen",
    "validation",
    "policy",
    "execution",
    "aggregation",
    "expression",
    "other",
]

BenchmarkCategory = Literal["in_scope", "out_of_scope", "adversarial"]

AuthorityOwner = Literal["llm", "deterministic", "hybrid", "none"]

AuthorityKey = Literal[
    "sql_gen",
    "validation",
    "policy",
    "aggregation",
]


AggregationOperation = Literal[
    "identity",
    "median",
    "average",
    "first",
    "last",
    "first_last",
    "percent_change",
    "count",
    "max",
    "ratio",
]


ResultType = Literal["scalar", "table"]


PrimaryModule = Literal[
    "sql_gen",
    "validation",
    "policy",
    "aggregation",
]


# ============================================================
# Module traces
# ============================================================


class SQLTrace(BaseModel):
    stage: SQLStage
    sql: str
    order: int

    class Config:
        extra = "forbid"


class LLMStageMetric(BaseModel):
    stage: LLMStage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0

    class Config:
        extra = "forbid"


class ValidationTrace(BaseModel):
    passed: bool
    checked_rules: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)

    sql_valid: Optional[bool] = None
    uses_only_allowed_tables: Optional[bool] = None
    unknown_table_refs: List[str] = Field(default_factory=list)

    has_required_joins: Optional[bool] = None
    has_required_window_constraints: Optional[bool] = None

    class Config:
        extra = "forbid"


class IntentTrace(BaseModel):
    raw_text: str = ""
    parsed: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "forbid"


class PolicyTrace(BaseModel):
    decision: Optional[Literal["allow", "refuse", "none"]] = None
    reason: Optional[str] = None
    raw_text: Optional[str] = None

    scope_category: Optional[
        Literal["in_scope", "out_of_scope", "unknown"]
    ] = None

    violations: List[str] = Field(default_factory=list)

    class Config:
        extra = "forbid"


class DiscoveryExecutionTrace(BaseModel):
    row_count: int = 0
    columns: List[str] = Field(default_factory=list)

    class Config:
        extra = "forbid"


class AggregationTrace(BaseModel):
    input_row_count: int = 0
    input_columns: List[str] = Field(default_factory=list)

    operation: Optional[AggregationOperation] = None

    output_shape: Optional[str] = None
    passed: Optional[bool] = None
    error: Optional[str] = None

    class Config:
        extra = "forbid"


class ExpressionTrace(BaseModel):
    answer_format: Optional[
        Literal["refuse", "error", "scalar", "table_preview", "empty"]
    ] = None

    rendered_from_row_count: int = 0

    class Config:
        extra = "forbid"


# ============================================================
# Main experiment record
# ============================================================


class ExperimentRecord(BaseModel):

    # --------------------------
    # Identity
    # --------------------------

    system_name: str
    question_id: str
    trial: int

    question: str
    benchmark_category: BenchmarkCategory
    should_refuse: bool

    primary_module: Optional[PrimaryModule] = None

    # --------------------------
    # Architecture configuration
    # --------------------------

    authority: Dict[AuthorityKey, AuthorityOwner]
    authority_notes: Optional[str] = None

    # --------------------------
    # Module traces
    # --------------------------

    sql_trace: List[SQLTrace] = Field(default_factory=list)
    discovery_source: Optional[Literal["deterministic", "llm"]] = None
    discovery_template_id: Optional[str] = None

    intent_trace: Optional[IntentTrace] = None
    validation_trace: Optional[ValidationTrace] = None
    discovery_validation_trace: Optional[ValidationTrace] = None
    final_validation_trace: Optional[ValidationTrace] = None
    policy_trace: Optional[PolicyTrace] = None
    policy_pre_trace: Optional[PolicyTrace] = None
    policy_post_trace: Optional[PolicyTrace] = None
    discovery_execution_trace: Optional[DiscoveryExecutionTrace] = None
    aggregation_trace: Optional[AggregationTrace] = None
    aggregation_plan_raw: Optional[Dict[str, Any]] = None
    aggregation_output_preview: List[Dict[str, Any]] = Field(default_factory=list)
    expression_trace: Optional[ExpressionTrace] = None

    # --------------------------
    # Final outcome
    # --------------------------

    refused: bool = False

    refusal_source: Optional[
        Literal[
            "policy",
            "validation",
            "aggregation",
            "expression",
            "other",
        ]
    ] = None

    execution_success: bool = False

    final_sql: Optional[str] = None
    final_row_count: int = 0
    final_error: Optional[str] = None

    failure_stage: Optional[FailureStage] = None

    answer_correct: Optional[bool] = None

    # --------------------------
    # Result structure
    # --------------------------

    result_type: Optional[ResultType] = None

    final_rows_preview: List[Dict[str, Any]] = Field(default_factory=list)
    final_columns: List[str] = Field(default_factory=list)

    answer_text: Optional[str] = None
    answer_format: Optional[str] = None

    # --------------------------
    # Reproducibility hooks
    # --------------------------

    final_sql_hash: Optional[str] = None
    output_hash: Optional[str] = None
    aggregation_output_hash: Optional[str] = None

    policy_compliant: Optional[bool] = None

    # --------------------------
    # Cost tracking
    # --------------------------

    llm_call_count: int = 0

    llm_total_prompt_tokens: int = 0
    llm_total_completion_tokens: int = 0
    llm_total_tokens: int = 0

    llm_total_latency_ms: int = 0

    llm_stage_metrics: List[LLMStageMetric] = Field(default_factory=list)

    db_call_count: int = 0
    db_total_latency_ms: int = 0

    db_error: Optional[str] = None
    db_bytes_processed: Optional[int] = None

    # --------------------------
    # Timing
    # --------------------------

    total_latency_ms: Optional[int] = None

    aggregation_latency_ms: int = 0
    expression_latency_ms: int = 0

    class Config:
        extra = "forbid"
