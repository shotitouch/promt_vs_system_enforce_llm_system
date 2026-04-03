from __future__ import annotations

import statistics
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _pick_value_column(rows: List[Dict[str, Any]]) -> Optional[str]:
    if not rows:
        return None
    if "valuenum" in rows[0]:
        return "valuenum"

    skip = {"stay_id", "subject_id", "hadm_id", "charttime", "lab_label", "itemid"}
    for col in rows[0].keys():
        if col in skip:
            continue
        if any(_to_float(r.get(col)) is not None for r in rows[:10]):
            return col
    return None


def _choose_operation(intent: Dict[str, Any]) -> tuple[str, Optional[str]]:
    question_type = str(intent.get("question_type", "") or "").lower()
    details = [str(x).lower() for x in (intent.get("details") or [])]
    text = " ".join(
        [
            question_type,
            str(intent.get("intent_summary", "") or "").lower(),
            str(intent.get("notes", "") or "").lower(),
            " ".join(details),
        ]
    )

    # Deterministic boundary: complex derived operations are unsupported in v1.
    if any(k in text for k in ["percent change", "percentage change", "proportion", "ratio", "increase"]):
        return "unsupported", "unsupported_derived_operation"

    if question_type == "count" or "how many" in text:
        return "count", None
    if question_type == "extreme":
        if any(k in text for k in ["lowest", "minimum", "min"]):
            return "min", None
        return "max", None
    if "first" in text and "last" in text:
        return "first_last", None
    if "first" in text:
        return "first", None
    if "last" in text:
        return "last", None
    if "median" in text:
        return "median", None
    if any(k in text for k in ["average", "mean"]):
        return "average", None
    return "identity", None


def _group_key(row: Dict[str, Any]) -> Any:
    return row.get("stay_id", "__all__")


def _first_last(rows: List[Dict[str, Any]], value_col: str) -> List[Dict[str, Any]]:
    if not rows:
        return []
    if "charttime" not in rows[0]:
        raise ValueError("missing_required_temporal_column")

    buckets: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        buckets[_group_key(r)].append(r)

    out: List[Dict[str, Any]] = []
    for k, group in buckets.items():
        ordered = sorted(group, key=lambda r: str(r.get("charttime") or ""))
        first_v = _to_float(ordered[0].get(value_col))
        last_v = _to_float(ordered[-1].get(value_col))
        out.append(
            {
                "stay_id": None if k == "__all__" else k,
                "first_value": first_v,
                "last_value": last_v,
            }
        )
    return out


def _try_passthrough(rows: List[Dict[str, Any]], operation: str) -> Optional[List[Dict[str, Any]]]:
    if not rows:
        return []

    cols = set(rows[0].keys())

    scalar_map = {
        "count": {"count"},
        "average": {"average"},
        "median": {"median"},
        "min": {"min"},
        "max": {"max"},
    }

    if operation in scalar_map and cols == scalar_map[operation]:
        return rows

    if operation == "first" and {"stay_id", "first_value"}.issubset(cols):
        return [
            {
                "stay_id": r.get("stay_id"),
                "first_value": r.get("first_value"),
            }
            for r in rows
        ]

    if operation == "last" and {"stay_id", "last_value"}.issubset(cols):
        return [
            {
                "stay_id": r.get("stay_id"),
                "last_value": r.get("last_value"),
            }
            for r in rows
        ]

    if operation == "first_last" and {"stay_id", "first_value", "last_value"}.issubset(cols):
        return [
            {
                "stay_id": r.get("stay_id"),
                "first_value": r.get("first_value"),
                "last_value": r.get("last_value"),
            }
            for r in rows
        ]

    return None


def aggregate_rows(rows: List[Dict[str, Any]], intent: Dict[str, Any]) -> dict:
    start = time.perf_counter()
    columns = list(rows[0].keys()) if rows else []
    operation, op_error = _choose_operation(intent)
    plan_raw: Dict[str, Any] = {
        "operation": operation,
        "group_by": ["stay_id"] if operation in {"first", "last", "first_last"} else [],
        "order_by": "charttime" if operation in {"first", "last", "first_last"} else None,
    }

    if op_error:
        return {
            "passed": False,
            "error": op_error,
            "operation": None,
            "plan_raw": plan_raw,
            "rows": [],
            "output_preview": [],
            "columns": [],
            "output_shape": None,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "input_row_count": len(rows),
            "input_columns": columns,
        }

    if operation == "identity":
        out_rows = rows
    else:
        passthrough_rows = _try_passthrough(rows, operation)
        if passthrough_rows is not None:
            out_rows = passthrough_rows
        elif operation == "count":
            out_rows = [{"count": len(rows)}]
        else:
            value_col = _pick_value_column(rows)
            plan_raw["value_column"] = value_col
            if value_col is None:
                return {
                    "passed": False,
                    "error": "missing_required_value_column",
                    "operation": None,
                    "plan_raw": plan_raw,
                    "rows": [],
                    "output_preview": [],
                    "columns": [],
                    "output_shape": None,
                    "latency_ms": int((time.perf_counter() - start) * 1000),
                    "input_row_count": len(rows),
                    "input_columns": columns,
                }

            values = [_to_float(r.get(value_col)) for r in rows]
            values = [v for v in values if v is not None]
            if operation in {"average", "median", "min", "max"} and not values:
                return {
                    "passed": False,
                    "error": "no_usable_numeric_values",
                    "operation": None,
                    "plan_raw": plan_raw,
                    "rows": [],
                    "output_preview": [],
                    "columns": [],
                    "output_shape": None,
                    "latency_ms": int((time.perf_counter() - start) * 1000),
                    "input_row_count": len(rows),
                    "input_columns": columns,
                }

            if operation == "average":
                out_rows = [{"average": sum(values) / len(values)}]
            elif operation == "median":
                out_rows = [{"median": statistics.median(values)}]
            elif operation == "min":
                out_rows = [{"min": min(values)}]
            elif operation == "max":
                out_rows = [{"max": max(values)}]
            elif operation in {"first", "last", "first_last"}:
                first_last_rows = _first_last(rows, value_col)
                if operation == "first":
                    out_rows = [{"stay_id": r.get("stay_id"), "first_value": r.get("first_value")} for r in first_last_rows]
                elif operation == "last":
                    out_rows = [{"stay_id": r.get("stay_id"), "last_value": r.get("last_value")} for r in first_last_rows]
                else:
                    out_rows = first_last_rows
            else:
                return {
                    "passed": False,
                    "error": "unsupported_reducer_operation",
                    "operation": None,
                    "plan_raw": plan_raw,
                    "rows": [],
                    "output_preview": [],
                    "columns": [],
                    "output_shape": None,
                    "latency_ms": int((time.perf_counter() - start) * 1000),
                    "input_row_count": len(rows),
                    "input_columns": columns,
                }

    out_cols = list(out_rows[0].keys()) if out_rows else []
    output_shape = "scalar" if len(out_rows) == 1 and len(out_cols) == 1 else "table"
    return {
        "passed": True,
        "error": None,
        "operation": operation,
        "plan_raw": plan_raw,
        "rows": out_rows,
        "output_preview": out_rows[:5] if out_rows else [],
        "columns": out_cols,
        "output_shape": output_shape,
        "latency_ms": int((time.perf_counter() - start) * 1000),
        "input_row_count": len(rows),
        "input_columns": columns,
    }
