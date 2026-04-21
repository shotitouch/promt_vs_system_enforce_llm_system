from __future__ import annotations

import time
from typing import Any, Dict, List

from config import REDUCER_TOKEN_LIMIT
from llm.client import get_llm
from llm.contracts.reducer import ReductionPlan
from llm.prompts.reducer import build_reducer_planner_prompt
from modules.reducer_checker import check_reduction_plan


def _sample_distinct_non_null(values: List[Any], limit: int = 5) -> List[Any]:
    out: List[Any] = []
    seen = set()
    for value in values:
        if value is None:
            continue
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _infer_column_type(values: List[Any]) -> str:
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "unknown"

    if all(isinstance(v, bool) for v in non_null):
        return "boolean"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return "numeric"

    textish = [str(v) for v in non_null[:10]]
    if any(":" in v or "-" in v for v in textish):
        return "temporal_or_text"
    return "text"


def _summarize_raw_message(raw_msg: Any) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "content": getattr(raw_msg, "content", None),
        "tool_calls": getattr(raw_msg, "tool_calls", None),
    }

    if hasattr(raw_msg, "response_metadata"):
        summary["response_metadata"] = raw_msg.response_metadata

    return summary


def _summarize_plan_check(check_result: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = check_result.get("artifacts", {}) or {}
    artifact_kinds = {
        name: artifact.get("kind")
        for name, artifact in artifacts.items()
    }
    artifact_columns = {
        name: list(artifact.get("columns", []))
        for name, artifact in artifacts.items()
    }
    return {
        "passed": check_result.get("passed", False),
        "errors": list(check_result.get("errors", [])),
        "warnings": list(check_result.get("warnings", [])),
        "artifact_kinds": artifact_kinds,
        "artifact_columns": artifact_columns,
    }


def build_reducer_input_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    columns = list(rows[0].keys()) if rows else []
    sample_rows = rows[:3]

    column_profiles: List[Dict[str, Any]] = []
    for column in columns:
        values = [row.get(column) for row in rows[:25]]
        profile = {
            "name": column,
            "inferred_type": _infer_column_type(values),
            "non_null_count_in_sample": sum(1 for v in values if v is not None),
            "sample_values": _sample_distinct_non_null(values, limit=5),
        }
        column_profiles.append(profile)

    return {
        "input_artifact": "rows",
        "kind": "table",
        "row_count": len(rows),
        "columns": columns,
        "column_profiles": column_profiles,
        "sample_rows": sample_rows,
    }


def plan_reduction_hybrid(intent: Dict[str, Any], rows: List[Dict[str, Any]]) -> dict:
    reducer_input = build_reducer_input_summary(rows)
    prompt = build_reducer_planner_prompt(
        intent=intent,
        reducer_input=reducer_input,
    )

    llm = get_llm(max_tokens=REDUCER_TOKEN_LIMIT)
    structured_llm = llm.with_structured_output(
        ReductionPlan,
        include_raw=True,
        method="function_calling",
    )

    start = time.perf_counter()
    resp = structured_llm.invoke(prompt)
    end = time.perf_counter()

    latency_ms = (end - start) * 1000
    plan_obj = resp.get("parsed")
    raw_msg = resp.get("raw")
    parsing_error = resp.get("parsing_error")
    raw_summary = _summarize_raw_message(raw_msg)

    prompt_tokens = None
    completion_tokens = None
    total_tokens = None

    if hasattr(raw_msg, "response_metadata"):
        usage = raw_msg.response_metadata.get("token_usage")
        if usage:
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")

    llm_result = {
        "content": plan_obj.model_dump_json() if plan_obj is not None else str(raw_summary),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
    }

    if plan_obj is None:
        error = (
            "Reducer plan parsing failed. "
            f"parsing_error={parsing_error!r}; raw_summary={raw_summary!r}"
        )
        return {
            "passed": False,
            "error": error,
            "reducer_input": reducer_input,
            "plan": None,
            "plan_check": None,
            "plan_check_trace": None,
            "plan_raw_for_logging": raw_summary,
            "llm_result": llm_result,
        }

    check_result = check_reduction_plan(plan_obj, reducer_input)
    plan_check_trace = _summarize_plan_check(check_result)
    if not check_result["passed"]:
        error = (
            "Reducer plan check failed. "
            f"errors={check_result['errors']!r}; warnings={check_result['warnings']!r}"
        )
        return {
            "passed": False,
            "error": error,
            "reducer_input": reducer_input,
            "plan": plan_obj.model_dump(),
            "plan_check": check_result,
            "plan_check_trace": plan_check_trace,
            "plan_raw_for_logging": plan_obj.model_dump(),
            "llm_result": llm_result,
        }

    return {
        "passed": True,
        "error": None,
        "reducer_input": reducer_input,
        "plan": plan_obj.model_dump(),
        "plan_check": check_result,
        "plan_check_trace": plan_check_trace,
        "plan_raw_for_logging": plan_obj.model_dump(),
        "llm_result": llm_result,
    }
