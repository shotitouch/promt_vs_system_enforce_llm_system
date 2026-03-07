from __future__ import annotations

from typing import Any, Dict

from utils.metrics import (
    allowed_tables_check,
    has_icu_window,
    has_icustays_join,
    sql_valid_select,
)


def validate_sql(sql: str) -> Dict[str, Any]:
    uses_only_allowed_tables, unknown_table_refs = allowed_tables_check(sql)
    sql_valid = sql_valid_select(sql)
    has_required_joins = has_icustays_join(sql)
    has_required_window_constraints = has_icu_window(sql)

    failures = []
    if not sql_valid:
        failures.append("invalid_sql")
    if uses_only_allowed_tables is False:
        failures.append("unauthorized_table")
    if has_required_joins is False:
        failures.append("missing_required_join")
    if has_required_window_constraints is False:
        failures.append("missing_required_window_constraint")

    return {
        "passed": len(failures) == 0,
        "checked_rules": [
            "sql_valid",
            "uses_only_allowed_tables",
            "has_required_joins",
            "has_required_window_constraints",
        ],
        "failures": failures,
        "sql_valid": sql_valid,
        "uses_only_allowed_tables": uses_only_allowed_tables,
        "unknown_table_refs": unknown_table_refs or [],
        "has_required_joins": has_required_joins,
        "has_required_window_constraints": has_required_window_constraints,
    }


def is_valid_select_sql(sql: str) -> bool:
    # Compatibility helper
    return validate_sql(sql)["sql_valid"]


# Backward compatibility
def validate_select_sql(sql: str) -> bool:
    return is_valid_select_sql(sql)
