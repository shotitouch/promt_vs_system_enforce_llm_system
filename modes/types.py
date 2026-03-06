from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from experiment.logging_schema import (
    AggregationTrace,
    DiscoveryExecutionTrace,
    ExpressionTrace,
    IntentTrace,
    LLMStageMetric,
    PolicyTrace,
    SQLTrace,
    ValidationTrace,
)


class ModeResult(BaseModel):
    # ---------------------------
    # Execution state
    # ---------------------------
    refused: bool = False
    refusal_source: Optional[str] = None
    execution_success: bool = False
    final_output: Optional[str] = None
    final_error: Optional[str] = None
    failure_stage: Optional[str] = None

    # ---------------------------
    # Result shape
    # ---------------------------
    final_row_count: int = 0
    final_rows_preview: List[Dict[str, Any]] = Field(default_factory=list)
    final_columns: List[str] = Field(default_factory=list)

    # ---------------------------
    # LLM totals
    # ---------------------------
    llm_call_count: int = 0
    llm_total_prompt_tokens: int = 0
    llm_total_completion_tokens: int = 0
    llm_total_tokens: int = 0
    llm_total_latency_ms: float = 0.0

    # ✅ NEW: Per-layer LLM metrics
    llm_stage_metrics: List[LLMStageMetric] = Field(default_factory=list)

    # ---------------------------
    # DB cost
    # ---------------------------
    db_call_count: int = 0
    db_total_latency_ms: float = 0.0
    db_error: Optional[str] = None

    # ---------------------------
    # Expression layer
    # ---------------------------
    answer_text: Optional[str] = None
    answer_format: Optional[str] = None  # "refuse" | "error" | "scalar" | "table_preview" | "empty"
    expression_latency_ms: int = 0

    # ---------------------------
    # Traces
    # ---------------------------
    sql_trace: List[SQLTrace] = Field(default_factory=list)
    intent_trace: Optional[IntentTrace] = None
    validation_trace: Optional[ValidationTrace] = None
    discovery_validation_trace: Optional[ValidationTrace] = None
    final_validation_trace: Optional[ValidationTrace] = None
    policy_trace: Optional[PolicyTrace] = None
    discovery_execution_trace: Optional[DiscoveryExecutionTrace] = None
    aggregation_trace: Optional[AggregationTrace] = None
    expression_trace: Optional[ExpressionTrace] = None

    class Config:
        extra = "forbid"
