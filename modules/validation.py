from __future__ import annotations

from typing import Any, Dict

from utils.metrics import allowed_tables_check, sql_valid_select


def validate_sql(sql: str) -> Dict[str, Any]:
    sql_valid = sql_valid_select(sql)

    if not sql_valid:
        return {
            "passed": False,
            "checked_rules": [
                "sql_valid",
                "uses_only_allowed_tables",
            ],
            "failures": ["invalid_sql"],
            "sql_valid": False,
            "uses_only_allowed_tables": False,
            "unknown_table_refs": [],
            "has_required_joins": None,
            "has_required_window_constraints": None,
        }

    uses_only_allowed_tables, unknown_table_refs = allowed_tables_check(sql)

    failures = []
    if uses_only_allowed_tables is False:
        failures.append("unauthorized_table")

    return {
        "passed": len(failures) == 0,
        "checked_rules": [
            "sql_valid",
            "uses_only_allowed_tables",
        ],
        "failures": failures,
        "sql_valid": sql_valid,
        "uses_only_allowed_tables": uses_only_allowed_tables,
        "unknown_table_refs": unknown_table_refs or [],
        "has_required_joins": None,
        "has_required_window_constraints": None,
    }


def is_valid_select_sql(sql: str) -> bool:
    return validate_sql(sql)["sql_valid"]


# Backward compatibility
def validate_select_sql(sql: str) -> bool:
    return is_valid_select_sql(sql)
