from __future__ import annotations

from typing import Any, Dict, List


def validate_post_aggregation(
    intent: Dict[str, Any],
    operation: str | None,
    rows: List[Dict[str, Any]],
    columns: List[str],
    output_shape: str | None,
) -> Dict[str, Any]:
    failures: List[str] = []
    checked_rules = [
        "operation_matches_output_columns",
    ]

    if operation in {"first", "last", "first_last"} and rows:
        if "stay_id" not in columns:
            failures.append("missing_stay_id_for_per_stay_output")

    if operation == "first" and rows:
        if "first_value" not in columns:
            failures.append("missing_first_value_column")

    if operation == "last" and rows:
        if "last_value" not in columns:
            failures.append("missing_last_value_column")

    if operation == "first_last" and rows:
        needed = {"first_value", "last_value"}
        if not needed.issubset(set(columns)):
            failures.append("missing_first_last_columns")

    return {
        "passed": len(failures) == 0,
        "checked_rules": checked_rules,
        "failures": failures,
        "sql_valid": None,
        "uses_only_allowed_tables": None,
        "unknown_table_refs": [],
        "has_required_joins": None,
        "has_required_window_constraints": None,
    }
