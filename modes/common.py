import time
from typing import Literal

from experiment.logging_schema import (
    AggregationPlanCheckTrace,
    AggregationTrace,
    DiscoveryExecutionTrace,
    IntentTrace,
    LLMStageMetric,
    PolicyTrace,
    SQLTrace,
    ValidationTrace,
)
from llm.contracts.reducer import ReductionPlan
from modes.types import ModeResult
from modules.aggregation import aggregate_rows
from modules.execution import DBExecutionError, execute_sql
from modules.expression import format_answer
from modules.intent import extract_intent
from modules.policy import check_policy, check_policy_deterministic
from modules.post_validation import validate_post_aggregation
from modules.reducer_executor import ReducerExecutionError, execute_reduction_plan
from modules.reducer_hybrid import plan_reduction_hybrid
from modules.sql_generation import (
    build_discovery_sql,
    build_final_sql,
    format_rows_as_text,
)
from modules.validation import validate_sql


PolicyMode = Literal["deterministic", "llm"]
ReducerMode = Literal["deterministic", "hybrid"]


def add_llm_usage(
    result: ModeResult, llm_result: dict, stage: str, latency_ms: int
) -> None:
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


def _handle_policy(
    *,
    question: str,
    intent_output: str,
    intent_parsed: dict,
    policy_mode: PolicyMode,
    result: ModeResult,
) -> bool:
    try:
        if policy_mode == "deterministic":
            policy_stage = check_policy_deterministic(
                question=question,
                intent=intent_parsed,
                intent_text=intent_output,
            )
            result.policy_pre_trace = PolicyTrace(
                decision=policy_stage["decision"],
                reason=policy_stage["reason"],
                raw_text=policy_stage["raw_text"],
                scope_category=policy_stage["scope_category"],
                violations=policy_stage["violations"],
            )
        else:
            start = time.perf_counter()
            policy_stage = check_policy(question=question, intent_text=intent_output)
            latency_ms = int((time.perf_counter() - start) * 1000)
            add_llm_usage(
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
            return False
        return True
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "policy"
        return False


def _run_discovery(
    *,
    intent_parsed: dict,
    result: ModeResult,
    trace_order: int,
) -> tuple[bool, str, int]:
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
        return False, "", trace_order

    if discovery_sql.upper() == "SKIP":
        return True, "Discovery skipped.", trace_order

    discovery_validation = validate_sql(discovery_sql)
    result.discovery_validation_trace = ValidationTrace(**discovery_validation)
    result.validation_trace = result.discovery_validation_trace
    if not discovery_validation["passed"]:
        result.final_error = "Discovery SQL failed validation"
        result.failure_stage = "validation"
        return False, "", trace_order

    try:
        result.db_call_count += 1
        exec_result = execute_sql(discovery_sql)
    except DBExecutionError as e:
        result.final_error = str(e)
        result.failure_stage = "execution"
        result.db_error = str(e)
        result.db_total_latency_ms += e.latency_ms
        return False, "", trace_order
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "execution"
        result.db_error = str(e)
        return False, "", trace_order

    result.db_total_latency_ms += exec_result["latency_ms"]
    discovery_rows = exec_result["rows"]
    result.discovery_execution_trace = DiscoveryExecutionTrace(
        row_count=len(discovery_rows),
        columns=list(discovery_rows[0].keys()) if discovery_rows else [],
    )
    return True, format_rows_as_text(discovery_rows), trace_order


def _run_final_sql(
    *,
    question: str,
    discovery_block: str,
    intent_output: str,
    result: ModeResult,
    trace_order: int,
) -> tuple[bool, list[dict], int]:
    try:
        start = time.perf_counter()
        final_stage = build_final_sql(
            question=question,
            discovery_context=discovery_block,
            intent_context=intent_output,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        add_llm_usage(
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
        return False, [], trace_order

    final_validation = validate_sql(final_sql)
    result.validation_trace = ValidationTrace(**final_validation)
    result.final_validation_trace = result.validation_trace
    if not final_validation["passed"]:
        result.final_error = "Final SQL failed validation"
        result.failure_stage = "validation"
        return False, [], trace_order

    try:
        result.db_call_count += 1
        exec_result = execute_sql(final_sql)
    except DBExecutionError as e:
        result.final_error = str(e)
        result.failure_stage = "execution"
        result.db_error = str(e)
        result.db_total_latency_ms += e.latency_ms
        return False, [], trace_order
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "execution"
        result.db_error = str(e)
        return False, [], trace_order

    result.db_total_latency_ms += exec_result["latency_ms"]
    return True, exec_result["rows"], trace_order


def _run_deterministic_reducer(
    *,
    rows: list[dict],
    intent_parsed: dict,
    result: ModeResult,
) -> tuple[bool, list[dict], str | None]:
    try:
        aggregation = aggregate_rows(rows=rows, intent=intent_parsed)
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "aggregation"
        return False, [], None

    result.aggregation_latency_ms = aggregation["latency_ms"]
    result.aggregation_plan_raw = aggregation.get("plan_raw")
    result.aggregation_output_preview = aggregation.get("output_preview", [])
    result.aggregation_trace = AggregationTrace(
        input_row_count=aggregation["input_row_count"],
        input_columns=aggregation["input_columns"],
        operation=aggregation["operation"],
        reducer_mode="deterministic",
        output_shape=aggregation["output_shape"],
        passed=aggregation["passed"],
        error=aggregation["error"],
    )
    if not aggregation["passed"]:
        result.final_error = aggregation["error"] or "aggregation_failed"
        result.failure_stage = "aggregation"
        return False, [], None

    return True, aggregation["rows"], aggregation["output_shape"]


def _run_hybrid_reducer(
    *,
    rows: list[dict],
    intent_parsed: dict,
    result: ModeResult,
) -> tuple[bool, list[dict], str | None]:
    try:
        planning = plan_reduction_hybrid(intent=intent_parsed, rows=rows)
    except Exception as e:
        result.final_error = str(e)
        result.failure_stage = "aggregation"
        result.aggregation_trace = AggregationTrace(
            input_row_count=len(rows),
            input_columns=list(rows[0].keys()) if rows else [],
            operation=None,
            output_shape=None,
            passed=False,
            error=str(e),
        )
        return False, [], None

    add_llm_usage(
        result,
        planning["llm_result"],
        stage="aggregation",
        latency_ms=int(planning["llm_result"]["latency_ms"]),
    )
    result.aggregation_input_summary = planning.get("reducer_input")
    result.aggregation_plan_raw = planning.get("plan_raw_for_logging")
    if planning.get("plan_check_trace") is not None:
        result.aggregation_plan_check = AggregationPlanCheckTrace(
            **planning["plan_check_trace"]
        )

    plan = planning.get("plan") or {}
    plan_status = plan.get("status")
    step_count = len(plan.get("steps", [])) if planning.get("plan") else None
    final_artifact = plan.get("final_artifact")
    final_kind = plan.get("final_kind")

    if not planning["passed"]:
        failure_substage = "planning"
        hybrid_operation = "hybrid_parse"
        if planning.get("plan_check_trace") is not None:
            failure_substage = "plan_check"
            hybrid_operation = "hybrid_plan_check"
        result.final_error = planning["error"]
        result.failure_stage = "aggregation"
        result.aggregation_trace = AggregationTrace(
            input_row_count=len(rows),
            input_columns=list(rows[0].keys()) if rows else [],
            operation=None,
            reducer_mode="hybrid",
            hybrid_operation=hybrid_operation,
            plan_status=plan_status,
            step_count=step_count,
            final_artifact=final_artifact,
            final_kind=final_kind,
            failure_substage=failure_substage,
            output_shape=None,
            passed=False,
            error=planning["error"],
        )
        return False, [], None

    try:
        start = time.perf_counter()
        execution = execute_reduction_plan(
            ReductionPlan.model_validate(planning["plan"]),
            rows,
        )
        result.aggregation_latency_ms = int((time.perf_counter() - start) * 1000)
    except ReducerExecutionError as e:
        failure_substage = "execution"
        hybrid_operation = "hybrid_execute"
        if plan_status == "no_reduction_needed":
            hybrid_operation = "hybrid_no_reduction_needed"
        result.final_error = str(e)
        result.failure_stage = "aggregation"
        result.aggregation_trace = AggregationTrace(
            input_row_count=len(rows),
            input_columns=list(rows[0].keys()) if rows else [],
            operation=None,
            reducer_mode="hybrid",
            hybrid_operation=hybrid_operation,
            plan_status=plan_status,
            step_count=step_count,
            final_artifact=final_artifact,
            final_kind=final_kind,
            failure_substage=failure_substage,
            output_shape=None,
            passed=False,
            error=str(e),
        )
        return False, [], None
    except Exception as e:
        failure_substage = "execution"
        hybrid_operation = "hybrid_execute"
        if plan_status == "no_reduction_needed":
            hybrid_operation = "hybrid_no_reduction_needed"
        result.final_error = str(e)
        result.failure_stage = "aggregation"
        result.aggregation_trace = AggregationTrace(
            input_row_count=len(rows),
            input_columns=list(rows[0].keys()) if rows else [],
            operation=None,
            reducer_mode="hybrid",
            hybrid_operation=hybrid_operation,
            plan_status=plan_status,
            step_count=step_count,
            final_artifact=final_artifact,
            final_kind=final_kind,
            failure_substage=failure_substage,
            output_shape=None,
            passed=False,
            error=str(e),
        )
        return False, [], None

    aggregated_rows = execution["rows"]
    hybrid_operation = "hybrid_execute"
    if plan_status == "no_reduction_needed":
        hybrid_operation = "hybrid_no_reduction_needed"
    result.aggregation_output_preview = aggregated_rows[:5] if aggregated_rows else []
    result.aggregation_trace = AggregationTrace(
        input_row_count=len(rows),
        input_columns=list(rows[0].keys()) if rows else [],
        operation=None,
        reducer_mode="hybrid",
        hybrid_operation=hybrid_operation,
        plan_status=plan_status,
        step_count=step_count,
        final_artifact=final_artifact,
        final_kind=final_kind,
        failure_substage=None,
        output_shape=execution["kind"],
        passed=True,
        error=None,
    )
    return True, aggregated_rows, execution["kind"]


def run_mode(
    *,
    question: str,
    policy_mode: PolicyMode,
    reducer_mode: ReducerMode,
) -> ModeResult:
    result = ModeResult(
        refused=False,
        refusal_source=None,
        policy_trace=None,
        aggregation_trace=None,
    )
    trace_order = 1

    intent_output = ""
    intent_parsed = {}
    try:
        start = time.perf_counter()
        intent_stage = extract_intent(question=question)
        latency_ms = int((time.perf_counter() - start) * 1000)
        add_llm_usage(result, intent_stage, stage="intent", latency_ms=latency_ms)
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

    if not _handle_policy(
        question=question,
        intent_output=intent_output,
        intent_parsed=intent_parsed,
        policy_mode=policy_mode,
        result=result,
    ):
        return format_answer(result)

    discovery_ok, discovery_block, trace_order = _run_discovery(
        intent_parsed=intent_parsed,
        result=result,
        trace_order=trace_order,
    )
    if not discovery_ok:
        return format_answer(result)

    final_ok, rows, trace_order = _run_final_sql(
        question=question,
        discovery_block=discovery_block,
        intent_output=intent_output,
        result=result,
        trace_order=trace_order,
    )
    if not final_ok:
        return format_answer(result)

    if reducer_mode == "deterministic":
        reduce_ok, aggregated_rows, output_shape = _run_deterministic_reducer(
            rows=rows,
            intent_parsed=intent_parsed,
            result=result,
        )
    else:
        reduce_ok, aggregated_rows, output_shape = _run_hybrid_reducer(
            rows=rows,
            intent_parsed=intent_parsed,
            result=result,
        )
    if not reduce_ok:
        return format_answer(result)

    result.final_row_count = len(aggregated_rows)
    result.final_rows_preview = aggregated_rows[:5] if aggregated_rows else []
    result.final_columns = list(aggregated_rows[0].keys()) if aggregated_rows else []
    result.execution_success = True

    post_validation = validate_post_aggregation(
        intent=intent_parsed,
        operation=result.aggregation_trace.operation if result.aggregation_trace else None,
        rows=aggregated_rows,
        columns=result.final_columns,
        output_shape=output_shape,
    )
    result.post_validation_trace = ValidationTrace(**post_validation)
    if not post_validation["passed"]:
        result.final_error = "Post-aggregation validation failed"
        result.failure_stage = "validation"
        return format_answer(result)

    return format_answer(result)
