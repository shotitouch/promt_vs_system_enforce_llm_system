# experiment/logging_schema.py

from pydantic import BaseModel, Field
from typing import Optional, List
from modes.types import SQLTrace
from modes.types import LLMStageMetric

# ---------------------------
# Main Experiment Record
# ---------------------------

class ExperimentRecord(BaseModel):
    mode: str
    question_id: str
    trial: int
    question: str
    should_refuse: bool

    # ---------------------------
    # SQL trace (ordered stages)
    # ---------------------------
    sql_trace: List[SQLTrace] = Field(default_factory=list)

    # ---------------------------
    # LLM totals (mode-level)
    # ---------------------------
    llm_call_count: int = 0
    llm_total_prompt_tokens: int = 0
    llm_total_completion_tokens: int = 0
    llm_total_tokens: int = 0
    llm_total_latency_ms: int = 0

    # Per-layer LLM metrics (authority-aware)
    llm_stage_metrics: List[LLMStageMetric] = Field(default_factory=list)

    # ---------------------------
    # Database cost
    # ---------------------------
    db_call_count: int = 0
    db_total_latency_ms: int = 0

    # ---------------------------
    # End-to-end latency
    # ---------------------------
    total_latency_ms: Optional[int] = None

    # ---------------------------
    # Execution outcome
    # ---------------------------
    final_output: Optional[str] = None
    refused: bool = False
    execution_success: bool = False
    final_row_count: int = 0
    final_error: Optional[str] = None

    # ---------------------------
    # Structural validation metrics
    # ---------------------------
    sql_valid: Optional[bool] = None
    has_icu_window: Optional[bool] = None
    has_icustays_join: Optional[bool] = None
    uses_only_allowed_tables: Optional[bool] = None
    unknown_table_refs: Optional[List[str]] = None
    final_sql_hash: Optional[str] = None

    # ---------------------------
    # Expression layer output
    # ---------------------------
    answer_text: Optional[str] = None
    answer_format: Optional[str] = None
    expression_latency_ms: int = 0

    class Config:
        extra = "forbid"