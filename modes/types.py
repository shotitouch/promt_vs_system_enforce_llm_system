from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class LLMStageMetric(BaseModel):
    stage: str  # e.g. "discovery", "final", "expression", etc.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0

    class Config:
        extra = "forbid"

class SQLTrace(BaseModel):
    stage: str
    sql: str
    order: int


class ModeResult(BaseModel):
    # ---------------------------
    # Execution state
    # ---------------------------
    refused: bool = False
    execution_success: bool = False
    final_output: Optional[str] = None
    final_error: Optional[str] = None

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

    class Config:
        extra = "forbid"