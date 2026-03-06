import time

from modes.types import ModeResult
from experiment.logging_schema import (
    DiscoveryExecutionTrace,
    IntentTrace,
    LLMStageMetric,
    PolicyTrace,
    SQLTrace,
    ValidationTrace,
)
from modules.execution import DBExecutionError, execute_sql
from modules.expression import finalize_expression
from modules.intent import run_intent_stage
from modules.policy import run_policy_stage
from modules.sql_generation import (
    format_discovery_rows,
    run_discovery_sql_stage,
    run_final_sql_stage,
)
from modules.validation import validate_select_sql


def _add_llm_usage(result: ModeResult, llm_result: dict, stage: str, latency_ms: int) -> None:
    prompt_tokens = llm_result.get("prompt_tokens", 0) or 0
    completion_tokens = llm_result.get("completion_tokens", 0) or 0
    total_tokens = llm_result.get("total_tokens", 0) or 0

    result.llm_call_count += 1
    result.llm_total_prompt_tokens += prompt_tokens
    result.llm_total_completion_tokens += completion_tokens
    result.llm_total_tokens += total_tokens
    result.llm_total_latency_ms += latency_ms

    result.llm_stage_metrics.append(
        LLMStageMetric(
            stage=stage,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )
    )


def mode3_answer(question: str) -> ModeResult:
    """
    Mode 3 orchestration:
    - Intent (LLM)
    - Policy (LLM)
    - Discovery SQL (LLM)
    - Execute discovery SQL
    - Final SQL (LLM)
    - Deterministic validation
    - Execute final SQL
    - Deterministic expression
    """

    result = ModeResult(
        refused=False,
        refusal_source=None,
        policy_trace=None,
        aggregation_trace=None,
    )
    trace_order = 1

    # 0) Intent
    intent_output = ""
    try:
        start = time.perf_counter()
        intent_stage = run_intent_stage(question=question)
        latency_ms = int((time.perf_counter() - start) * 1000)
        _add_llm_usage(result, intent_stage, stage="intent", latency_ms=latency_ms)
        intent_output = (intent_stage.get("content", "") or "").strip()
        result.intent_trace = IntentTrace(
            raw_text=intent_output,
            parsed=intent_stage.get("intent", {}) or {},
        )
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "other"
        return finalize_expression(result)

    # 1) Policy
    try:
        start = time.perf_counter()
        policy_stage = run_policy_stage(question=question, intent_text=intent_output)
        latency_ms = int((time.perf_counter() - start) * 1000)
        _add_llm_usage(
            result,
            policy_stage["llm_result"],
            stage="policy",
            latency_ms=latency_ms,
        )

        result.policy_trace = PolicyTrace(
            decision=policy_stage["decision"],
            reason=policy_stage["reason"],
            raw_text=policy_stage["llm_result"].get("content", ""),
            scope_category=policy_stage["scope_category"],
            violations=policy_stage["violations"],
        )

        if policy_stage["decision"] == "refuse":
            result.refused = True
            result.refusal_source = "policy"
            result.failure_stage = "policy"
            return finalize_expression(result)

    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "policy"
        return finalize_expression(result)

    # 2) Discovery SQL
    try:
        start = time.perf_counter()
        discovery_stage = run_discovery_sql_stage(question=question)
        latency_ms = int((time.perf_counter() - start) * 1000)
        _add_llm_usage(
            result,
            discovery_stage["llm_result"],
            stage="discovery",
            latency_ms=latency_ms,
        )

        discovery_sql = discovery_stage["sql"]
        result.sql_trace.append(
            SQLTrace(stage="discovery", sql=discovery_sql, order=trace_order)
        )
        trace_order += 1
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "discovery"
        return finalize_expression(result)

    if discovery_sql.upper() == "SKIP":
        discovery_block = "Discovery skipped."
    else:
        if not validate_select_sql(discovery_sql):
            result.final_error = "Invalid discovery SQL (expected SELECT)"
            result.failure_stage = "validation"
            result.discovery_validation_trace = ValidationTrace(
                passed=False,
                checked_rules=["sql_valid"],
                failures=["invalid_discovery_sql"],
                sql_valid=False,
            )
            result.validation_trace = result.discovery_validation_trace
            return finalize_expression(result)

        try:
            result.db_call_count += 1
            exec_result = execute_sql(discovery_sql)
        except DBExecutionError as e:
            result.final_error = str(e)
            result.failure_stage = "execution"
            result.db_error = str(e)
            result.db_total_latency_ms += e.latency_ms
            return finalize_expression(result)
        except Exception as e:
            result.final_error = str(e)
            result.failure_stage = "execution"
            result.db_error = str(e)
            return finalize_expression(result)

        result.db_total_latency_ms += exec_result["latency_ms"]
        discovery_rows = exec_result["rows"]
        result.discovery_execution_trace = DiscoveryExecutionTrace(
            row_count=len(discovery_rows),
            columns=list(discovery_rows[0].keys()) if discovery_rows else [],
        )
        discovery_block = format_discovery_rows(discovery_rows)

    # 3) Final SQL
    try:
        start = time.perf_counter()
        final_stage = run_final_sql_stage(
            question=question,
            discovery_context=discovery_block,
            intent_context=intent_output,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        _add_llm_usage(
            result,
            final_stage["llm_result"],
            stage="final",
            latency_ms=latency_ms,
        )

        final_output = final_stage["sql"]
        result.sql_trace.append(
            SQLTrace(stage="final", sql=final_output, order=trace_order)
        )
        trace_order += 1
        result.final_output = final_output
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "sql_gen"
        return finalize_expression(result)

    # 4) Deterministic validation
    sql_valid = validate_select_sql(final_output)
    result.validation_trace = ValidationTrace(
        passed=sql_valid,
        checked_rules=["sql_valid"],
        failures=[] if sql_valid else ["non_select_final_sql"],
        sql_valid=sql_valid,
    )
    result.final_validation_trace = result.validation_trace
    if not sql_valid:
        result.final_error = "Non-SELECT SQL generated"
        result.failure_stage = "validation"
        return finalize_expression(result)

    # 5) Final execution
    try:
        result.db_call_count += 1
        exec_result = execute_sql(final_output)
    except DBExecutionError as e:
        result.final_error = str(e)
        result.failure_stage = "execution"
        result.db_error = str(e)
        result.db_total_latency_ms += e.latency_ms
        return finalize_expression(result)
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "execution"
        result.db_error = str(e)
        return finalize_expression(result)

    rows = exec_result["rows"]
    result.db_total_latency_ms += exec_result["latency_ms"]
    result.final_row_count = len(rows)
    result.execution_success = True
    result.final_rows_preview = rows[:5] if rows else []
    result.final_columns = list(result.final_rows_preview[0].keys()) if result.final_rows_preview else []

    return finalize_expression(result)
