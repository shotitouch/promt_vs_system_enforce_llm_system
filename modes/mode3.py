# modes/mode3.py

import time
from llm.client import call_llm_raw
from llm.prompt_mode3 import (
    build_mode3_final_prompt,
    build_mode3_discovery_prompt,
)
from db.bigquery import run_raw_query
from utils.utils import clean_sql, is_select_sql
from utils.expression import express_mode_result
from modes.types import ModeResult, SQLTrace
from experiment.logging_schema import LLMStageMetric
from config import LONG_TOKEN_LIMIT


def mode3_answer(question: str, level: int = 1) -> ModeResult:
    """
    Mode 3:
    - Discovery LLM
    - Final SQL LLM
    - DB execution
    - Deterministic expression layer

    Pure architecture output (ModeResult).
    """

    if level not in (1, 2):
        raise ValueError("Mode3 level must be 1 or 2")

    result = ModeResult()
    trace_order = 1

    # -----------------------------
    # 1️⃣ DISCOVERY
    # -----------------------------
    try:
        discovery_prompt = build_mode3_discovery_prompt(question=question)

        llm_start = time.perf_counter()
        llm_result = call_llm_raw(prompt=discovery_prompt, question=question)
        llm_end = time.perf_counter()

        prompt_tokens = llm_result.get("prompt_tokens", 0) or 0
        completion_tokens = llm_result.get("completion_tokens", 0) or 0
        total_tokens = llm_result.get("total_tokens", 0) or 0
        latency_ms = int((llm_end - llm_start) * 1000)

        # ---- totals ----
        result.llm_call_count += 1
        result.llm_total_prompt_tokens += prompt_tokens
        result.llm_total_completion_tokens += completion_tokens
        result.llm_total_tokens += total_tokens
        result.llm_total_latency_ms += latency_ms

        # ---- stage-level ----
        result.llm_stage_metrics.append(
            LLMStageMetric(
                stage="discovery",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )
        )

        discovery_sql = clean_sql(llm_result.get("content", "")).strip()

        result.sql_trace.append(
            SQLTrace(stage="discovery", sql=discovery_sql, order=trace_order)
        )
        trace_order += 1

        if discovery_sql.upper() == "REFUSE":
            result.refused = True
            result.final_output = discovery_sql
            return _finalize_with_expression(result)

        if discovery_sql.upper() == "SKIP":
            discovery_block = "Discovery skipped."
        else:
            if not is_select_sql(discovery_sql):
                result.final_error = "Invalid discovery SQL"
                return _finalize_with_expression(result)

            db_start = time.perf_counter()
            discovery_rows = run_raw_query(discovery_sql)
            db_end = time.perf_counter()

            result.db_call_count += 1
            result.db_total_latency_ms += int((db_end - db_start) * 1000)

            discovery_block = format_discovery_rows(discovery_rows)

    except Exception as e:
        result.final_error = str(e)
        return _finalize_with_expression(result)

    # -----------------------------
    # 2️⃣ FINAL SQL
    # -----------------------------
    try:
        final_prompt = build_mode3_final_prompt(
            level=level,
            discovery_context=discovery_block,
            question=question,
        )

        llm_start = time.perf_counter()
        llm_result = call_llm_raw(
            prompt=final_prompt,
            question=question,
            max_tokens=LONG_TOKEN_LIMIT,
        )
        llm_end = time.perf_counter()

        prompt_tokens = llm_result.get("prompt_tokens", 0) or 0
        completion_tokens = llm_result.get("completion_tokens", 0) or 0
        total_tokens = llm_result.get("total_tokens", 0) or 0
        latency_ms = int((llm_end - llm_start) * 1000)

        # ---- totals ----
        result.llm_call_count += 1
        result.llm_total_prompt_tokens += prompt_tokens
        result.llm_total_completion_tokens += completion_tokens
        result.llm_total_tokens += total_tokens
        result.llm_total_latency_ms += latency_ms

        # ---- stage-level ----
        result.llm_stage_metrics.append(
            LLMStageMetric(
                stage="final",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )
        )

        final_output = clean_sql(llm_result.get("content", "")).strip()

        result.sql_trace.append(
            SQLTrace(stage="final", sql=final_output, order=trace_order)
        )
        trace_order += 1

        result.final_output = final_output

        if final_output.upper() == "REFUSE":
            result.refused = True
            return _finalize_with_expression(result)

        if not is_select_sql(final_output):
            result.final_error = "Non-SELECT SQL generated"
            return _finalize_with_expression(result)

        db_start = time.perf_counter()
        rows = run_raw_query(final_output)
        db_end = time.perf_counter()

        result.db_call_count += 1
        result.db_total_latency_ms += int((db_end - db_start) * 1000)

        result.final_row_count = len(rows)
        result.execution_success = True

        preview = rows[:5] if rows else []
        result.final_rows_preview = preview
        result.final_columns = list(preview[0].keys()) if preview else []

    except Exception as e:
        result.final_error = str(e)

    return _finalize_with_expression(result)


# ----------------------------------------
# Deterministic expression integration
# ----------------------------------------

def _finalize_with_expression(result: ModeResult) -> ModeResult:
    """
    Applies deterministic expression layer and returns final ModeResult.
    """
    expr = express_mode_result(result)

    result.answer_text = expr["answer_text"]
    result.answer_format = expr["answer_format"]
    result.expression_latency_ms = expr["expression_latency_ms"]

    return result


# ----------------------------------------
# Helper
# ----------------------------------------

def format_discovery_rows(rows, max_rows: int = 50) -> str:
    if not rows:
        return "No discovery results returned."

    rows = rows[:max_rows]
    columns = list(rows[0].keys())
    if not columns:
        return "Discovery returned rows with no columns."

    header = " | ".join(columns)
    lines = [header]
    for r in rows:
        line = " | ".join(str(r.get(col)) for col in columns)
        lines.append(line)
    return "\n".join(lines)