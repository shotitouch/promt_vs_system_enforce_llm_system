# modes/mode3.py

import json
import time
from typing import Any, Dict, Optional

from llm.client import call_llm_raw
from llm.common import (
    build_discovery_prompt,
    build_sql_after_discovery_prompt,
    SQL_PROMPT_FINALITY,
    # You MUST implement these 2 builders (or rename imports to your actual functions):
    build_intent_prompt,
    build_policy_prompt,
)
from db.bigquery import run_raw_query
from utils.utils import clean_sql, is_select_sql
from utils.expression import express_mode_result
from modes.types import ModeResult
from experiment.logging_schema import (
    ExpressionTrace,
    LLMStageMetric,
    SQLTrace,
    ValidationTrace,
    PolicyTrace,
)
from config import LONG_TOKEN_LIMIT


# ----------------------------------------
# Helper: robust parse for policy JSON
# ----------------------------------------

def _safe_parse_json(s: str) -> Optional[Dict[str, Any]]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        # Try to extract a JSON object from surrounding text
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except Exception:
                return None
        return None


def mode3_answer(question: str) -> ModeResult:
    """
    Mode 3 (updated):
    - Intent LLM
    - Policy module (LLM) after intent (reasoning-stage scope enforcement)
    - Discovery SQL LLM
    - Final SQL LLM
    - Deterministic validation (minimal but logged)
    - DB execution
    - Deterministic expression layer
    - No aggregation module
    """

    result = ModeResult(
        refused=False,
        refusal_source=None,
        policy_trace=None,
        aggregation_trace=None,  # Mode3 has no aggregation
    )

    trace_order = 1

    # -----------------------------
    # 0️⃣ INTENT
    # -----------------------------
    intent_output = ""
    try:
        intent_prompt = build_intent_prompt(question=question)

        llm_start = time.perf_counter()
        llm_result = call_llm_raw(prompt=intent_prompt)
        llm_end = time.perf_counter()

        prompt_tokens = llm_result.get("prompt_tokens", 0) or 0
        completion_tokens = llm_result.get("completion_tokens", 0) or 0
        total_tokens = llm_result.get("total_tokens", 0) or 0
        latency_ms = int((llm_end - llm_start) * 1000)

        # totals
        result.llm_call_count += 1
        result.llm_total_prompt_tokens += prompt_tokens
        result.llm_total_completion_tokens += completion_tokens
        result.llm_total_tokens += total_tokens
        result.llm_total_latency_ms += latency_ms

        # stage metrics
        result.llm_stage_metrics.append(
            LLMStageMetric(
                stage="intent",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )
        )

        intent_output = (llm_result.get("content", "") or "").strip()

    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "other"  # keep consistent if ModeResult lacks "intent"
        return _finalize_with_expression(result)

    # -----------------------------
    # 0️⃣ POLICY (after intent)
    # -----------------------------
    try:
        policy_prompt = build_policy_prompt(question=question, intent=intent_output)

        llm_start = time.perf_counter()
        llm_result = call_llm_raw(prompt=policy_prompt)
        llm_end = time.perf_counter()

        prompt_tokens = llm_result.get("prompt_tokens", 0) or 0
        completion_tokens = llm_result.get("completion_tokens", 0) or 0
        total_tokens = llm_result.get("total_tokens", 0) or 0
        latency_ms = int((llm_end - llm_start) * 1000)

        # totals
        result.llm_call_count += 1
        result.llm_total_prompt_tokens += prompt_tokens
        result.llm_total_completion_tokens += completion_tokens
        result.llm_total_tokens += total_tokens
        result.llm_total_latency_ms += latency_ms

        # stage metrics
        result.llm_stage_metrics.append(
            LLMStageMetric(
                stage="policy",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )
        )

        raw = (llm_result.get("content", "") or "").strip()
        payload = _safe_parse_json(raw)

        # Expected JSON format (recommended):
        # {
        #   "decision": "allow" | "refuse",
        #   "scope_category": "in_scope" | "out_of_scope" | "unknown",
        #   "reason": "...",
        #   "violations": ["..."]
        # }
        decision = None
        scope_category = None
        reason = None
        violations = []

        if isinstance(payload, dict):
            decision = payload.get("decision")
            scope_category = payload.get("scope_category")
            reason = payload.get("reason")
            violations = payload.get("violations") or []
        else:
            # fallback heuristic if model didn't output JSON
            low = raw.lower()
            if "refuse" in low:
                decision = "refuse"
            elif "allow" in low:
                decision = "allow"
            else:
                decision = "none"
            scope_category = "unknown"
            reason = raw[:500]
            violations = []

        # normalize
        decision = (decision or "none").strip().lower()
        if decision not in ("allow", "refuse", "none"):
            decision = "none"

        if scope_category:
            scope_category = scope_category.strip().lower()
            if scope_category not in ("in_scope", "out_of_scope", "unknown"):
                scope_category = "unknown"
        else:
            scope_category = "unknown"

        if not isinstance(violations, list):
            violations = [str(violations)]

        result.policy_trace = PolicyTrace(
            decision=decision,
            reason=(reason or "")[:1000] if reason else None,
            scope_category=scope_category,
            violations=[str(v) for v in violations][:20],
        )

        if decision == "refuse":
            result.refused = True
            result.refusal_source = "policy"
            result.failure_stage = "policy"
            return _finalize_with_expression(result)

    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "policy"
        return _finalize_with_expression(result)

    # -----------------------------
    # 1️⃣ DISCOVERY
    # -----------------------------
    discovery_sql = ""
    try:
        discovery_prompt = build_discovery_prompt(question=question)

        llm_start = time.perf_counter()
        llm_result = call_llm_raw(prompt=discovery_prompt)
        llm_end = time.perf_counter()

        prompt_tokens = llm_result.get("prompt_tokens", 0) or 0
        completion_tokens = llm_result.get("completion_tokens", 0) or 0
        total_tokens = llm_result.get("total_tokens", 0) or 0
        latency_ms = int((llm_end - llm_start) * 1000)

        # totals
        result.llm_call_count += 1
        result.llm_total_prompt_tokens += prompt_tokens
        result.llm_total_completion_tokens += completion_tokens
        result.llm_total_tokens += total_tokens
        result.llm_total_latency_ms += latency_ms

        # stage metrics
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

    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "discovery"
        return _finalize_with_expression(result)

    # materialize discovery context
    if discovery_sql.upper() == "SKIP":
        discovery_block = "Discovery skipped."
    else:
        # deterministic validation for discovery SQL (logged)
        if not is_select_sql(discovery_sql):
            result.final_error = "Invalid discovery SQL (expected SELECT)"
            result.failure_stage = "validation"
            result.validation_trace = ValidationTrace(
                passed=False,
                checked_rules=["sql_valid"],
                failures=["invalid_discovery_sql"],
                sql_valid=False,
            )
            return _finalize_with_expression(result)

        try:
            db_start = time.perf_counter()
            discovery_rows = run_raw_query(discovery_sql)
            db_end = time.perf_counter()
        except Exception as e:
            result.final_error = str(e)
            result.failure_stage = "execution"
            result.db_error = str(e)
            return _finalize_with_expression(result)

        result.db_call_count += 1
        result.db_total_latency_ms += int((db_end - db_start) * 1000)

        discovery_block = format_discovery_rows(discovery_rows)

    # -----------------------------
    # 2️⃣ FINAL SQL
    # -----------------------------
    final_output = ""
    try:
        final_prompt = build_sql_after_discovery_prompt(
            sql_prompt=SQL_PROMPT_FINALITY,
            discovery_context=discovery_block,
            question=question,
        )

        llm_start = time.perf_counter()
        llm_result = call_llm_raw(prompt=final_prompt, max_tokens=LONG_TOKEN_LIMIT)
        llm_end = time.perf_counter()

        prompt_tokens = llm_result.get("prompt_tokens", 0) or 0
        completion_tokens = llm_result.get("completion_tokens", 0) or 0
        total_tokens = llm_result.get("total_tokens", 0) or 0
        latency_ms = int((llm_end - llm_start) * 1000)

        # totals
        result.llm_call_count += 1
        result.llm_total_prompt_tokens += prompt_tokens
        result.llm_total_completion_tokens += completion_tokens
        result.llm_total_tokens += total_tokens
        result.llm_total_latency_ms += latency_ms

        # stage metrics
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

    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "sql_gen"
        return _finalize_with_expression(result)

    # -----------------------------
    # 3️⃣ DETERMINISTIC VALIDATION (logged)
    # -----------------------------
    # Minimal baseline rules for Mode3:
    # - SQL must be SELECT
    # (Your stricter rules like allowed tables / required joins can still be added later)
    sql_valid = is_select_sql(final_output)

    result.validation_trace = ValidationTrace(
        passed=sql_valid,
        checked_rules=["sql_valid"],
        failures=[] if sql_valid else ["non_select_final_sql"],
        sql_valid=sql_valid,
    )

    if not sql_valid:
        result.final_error = "Non-SELECT SQL generated"
        result.failure_stage = "validation"
        return _finalize_with_expression(result)

    # -----------------------------
    # 4️⃣ EXECUTION
    # -----------------------------
    try:
        db_start = time.perf_counter()
        rows = run_raw_query(final_output)
        db_end = time.perf_counter()
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "execution"
        result.db_error = str(e)
        return _finalize_with_expression(result)

    result.db_call_count += 1
    result.db_total_latency_ms += int((db_end - db_start) * 1000)

    result.final_row_count = len(rows)
    result.execution_success = True

    preview = rows[:5] if rows else []
    result.final_rows_preview = preview
    result.final_columns = list(preview[0].keys()) if preview else []

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

    result.expression_trace = ExpressionTrace(
        answer_format=result.answer_format,
        rendered_from_row_count=result.final_row_count,
    )

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