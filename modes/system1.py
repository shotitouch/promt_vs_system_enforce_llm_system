import time

from modes.types import ModeResult
from experiment.logging_schema import (
    AggregationTrace,
    DiscoveryExecutionTrace,
    IntentTrace,
    LLMStageMetric,
    PolicyTrace,
    SQLTrace,
    ValidationTrace,
)
from modules.aggregation import aggregate_rows
from modules.execution import DBExecutionError, execute_sql
from modules.expression import format_answer
from modules.intent import extract_intent
from modules.policy import check_policy
from modules.sql_generation import (
    build_discovery_sql,
    build_final_sql,
    format_rows_as_text,
)
from modules.validation import validate_sql


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


def system1_answer(question: str) -> ModeResult:
    """
    System 1 pipeline:
    Question
      -> Intent (LLM)
      -> Policy Pre (LLM)
      -> Discovery SQL (deterministic metadata lookup)
      -> Execute Discovery SQL
      -> Final SQL (LLM, intermediate-data oriented)
      -> Policy Post (LLM, checks planned SQL)
      -> SQL Validation (deterministic)
      -> Execute Final SQL
      -> Aggregation (deterministic, mandatory)
      -> Expression (deterministic formatting)
    """

    result = ModeResult(
        refused=False,
        refusal_source=None,
        policy_trace=None,
        aggregation_trace=None,
    )
    trace_order = 1

    # 0) Intent (LLM)
    intent_output = ""
    intent_parsed = {}
    try:
        start = time.perf_counter()
        intent_stage = extract_intent(question=question)
        latency_ms = int((time.perf_counter() - start) * 1000)
        _add_llm_usage(result, intent_stage, stage="intent", latency_ms=latency_ms)
        intent_output = (intent_stage.get("content", "") or "").strip()
        intent_parsed = intent_stage.get("intent", {}) or {}
        result.intent_trace = IntentTrace(
            raw_text=intent_output,
            parsed=intent_parsed,
        )
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "other"
        return format_answer(result)

    # 1) Policy Pre (LLM): check scope using question + intent
    try:
        start = time.perf_counter()
        policy_stage = check_policy(question=question, intent_text=intent_output)
        latency_ms = int((time.perf_counter() - start) * 1000)
        _add_llm_usage(
            result,
            policy_stage["llm_result"],
            stage="policy",
            latency_ms=latency_ms,
        )

        result.policy_pre_trace = PolicyTrace(
            decision=policy_stage["decision"],
            reason=policy_stage["reason"],
            raw_text=policy_stage["llm_result"].get("content", ""),
            scope_category=policy_stage["scope_category"],
            violations=policy_stage["violations"],
        )
        result.policy_trace = result.policy_pre_trace

        if policy_stage["decision"] == "refuse":
            result.refused = True
            result.refusal_source = "policy"
            result.failure_stage = "policy"
            return format_answer(result)

    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "policy"
        return format_answer(result)

    # 2) Discovery SQL (deterministic metadata lookup)
    try:
        discovery_stage = build_discovery_sql(intent=intent_parsed)
        discovery_sql = discovery_stage["sql"]
        result.discovery_source = discovery_stage.get("source")
        result.discovery_template_id = discovery_stage.get("template_id")
        result.sql_trace.append(
            SQLTrace(stage="discovery", sql=discovery_sql, order=trace_order)
        )
        trace_order += 1
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "discovery"
        return format_answer(result)

    if discovery_sql.upper() == "SKIP":
        discovery_block = "Discovery skipped."
    else:
        discovery_validation = validate_sql(discovery_sql)
        result.discovery_validation_trace = ValidationTrace(**discovery_validation)
        result.validation_trace = result.discovery_validation_trace
        if not discovery_validation["passed"]:
            result.final_error = "Discovery SQL failed validation"
            result.failure_stage = "validation"
            return format_answer(result)

        try:
            result.db_call_count += 1
            exec_result = execute_sql(discovery_sql)
        except DBExecutionError as e:
            result.final_error = str(e)
            result.failure_stage = "execution"
            result.db_error = str(e)
            result.db_total_latency_ms += e.latency_ms
            return format_answer(result)
        except Exception as e:
            result.final_error = str(e)
            result.failure_stage = "execution"
            result.db_error = str(e)
            return format_answer(result)

        result.db_total_latency_ms += exec_result["latency_ms"]
        discovery_rows = exec_result["rows"]
        result.discovery_execution_trace = DiscoveryExecutionTrace(
            row_count=len(discovery_rows),
            columns=list(discovery_rows[0].keys()) if discovery_rows else [],
        )
        discovery_block = format_rows_as_text(discovery_rows)

    # 3) Final SQL (LLM): generate aggregation-ready SQL
    try:
        start = time.perf_counter()
        final_stage = build_final_sql(
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

        final_sql = final_stage["sql"]
        result.sql_trace.append(
            SQLTrace(stage="final", sql=final_sql, order=trace_order)
        )
        trace_order += 1
        result.final_sql = final_sql
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "sql_gen"
        return format_answer(result)

    # 4) Policy Post (LLM): re-check scope using planned SQL
    try:
        start = time.perf_counter()
        policy_post_stage = check_policy(
            question=question,
            intent_text=intent_output,
            sql_text=final_sql,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        _add_llm_usage(
            result,
            policy_post_stage["llm_result"],
            stage="policy",
            latency_ms=latency_ms,
        )
        result.policy_post_trace = PolicyTrace(
            decision=policy_post_stage["decision"],
            reason=policy_post_stage["reason"],
            raw_text=policy_post_stage["llm_result"].get("content", ""),
            scope_category=policy_post_stage["scope_category"],
            violations=policy_post_stage["violations"],
        )
        if policy_post_stage["decision"] == "refuse":
            result.refused = True
            result.refusal_source = "policy"
            result.failure_stage = "policy"
            return format_answer(result)
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "policy"
        return format_answer(result)

    # 5) SQL Validation (deterministic)
    final_validation = validate_sql(final_sql)
    result.validation_trace = ValidationTrace(**final_validation)
    result.final_validation_trace = result.validation_trace
    if not final_validation["passed"]:
        result.final_error = "Final SQL failed validation"
        result.failure_stage = "validation"
        return format_answer(result)

    # 6) Execute Final SQL
    try:
        result.db_call_count += 1
        exec_result = execute_sql(final_sql)
    except DBExecutionError as e:
        result.final_error = str(e)
        result.failure_stage = "execution"
        result.db_error = str(e)
        result.db_total_latency_ms += e.latency_ms
        return format_answer(result)
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "execution"
        result.db_error = str(e)
        return format_answer(result)

    rows = exec_result["rows"]
    result.db_total_latency_ms += exec_result["latency_ms"]
    # 7) Aggregation (deterministic, mandatory)
    aggregation = aggregate_rows(rows=rows, intent=intent_parsed)
    result.aggregation_latency_ms = aggregation["latency_ms"]
    result.aggregation_plan_raw = aggregation.get("plan_raw")
    result.aggregation_output_preview = aggregation.get("output_preview", [])
    result.aggregation_trace = AggregationTrace(
        input_row_count=aggregation["input_row_count"],
        input_columns=aggregation["input_columns"],
        operation=aggregation["operation"],
        output_shape=aggregation["output_shape"],
        passed=aggregation["passed"],
        error=aggregation["error"],
    )
    if not aggregation["passed"]:
        result.final_error = aggregation["error"] or "aggregation_failed"
        result.failure_stage = "aggregation"
        return format_answer(result)

    aggregated_rows = aggregation["rows"]
    result.final_row_count = len(aggregated_rows)
    result.final_rows_preview = aggregated_rows[:5] if aggregated_rows else []
    result.final_columns = aggregation["columns"]
    result.execution_success = True

    # 8) Expression (deterministic formatting only)
    return format_answer(result)
