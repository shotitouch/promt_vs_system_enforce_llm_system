# utils/metrics.py

import hashlib
import re
from typing import List, Tuple, Dict, Any, Optional, Set

import sqlglot
from sqlglot import exp

# Allowed base tables in this project.
ALLOWED_TABLES = {
    "icustays",
    "labevents",
    "d_labitems",
}


# ---------
# SQL normalize + hash (for stability)
# ---------

def normalize_sql(sql: str) -> str:
    """Lightweight normalization for stable hashing."""
    s = (sql or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("`", "")
    s = s.lower()
    return s


def sql_hash(sql: str) -> str:
    """Short stable hash for comparing across trials."""
    norm = normalize_sql(sql)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]


def parse_sql_ast(sql: str):
    try:
        return sqlglot.parse_one(sql, read="bigquery")
    except Exception:
        return None


def sql_valid_select(sql: str) -> bool:
    return parse_sql_ast(sql) is not None


def _normalize_table_name(table: exp.Table) -> str:
    if table.this is None:
        return ""
    name = str(table.this).strip().lower()
    return name.strip("`\"")


def extract_table_refs(sql: str) -> List[str]:
    ast = parse_sql_ast(sql)
    if ast is None:
        return []

    cte_names: Set[str] = set()
    with_expr = ast.args.get("with_")
    if with_expr:
        for cte in with_expr.find_all(exp.CTE):
            if cte.alias_or_name:
                cte_names.add(cte.alias_or_name.lower())

    tables: List[str] = []
    for table in ast.find_all(exp.Table):
        name = _normalize_table_name(table)
        if not name:
            continue
        if name in cte_names:
            continue
        tables.append(name)

    return sorted(set(tables))


def allowed_tables_check(
    sql: str,
    allowed: Optional[set] = None,
) -> Tuple[bool, List[str]]:
    allowed = allowed or ALLOWED_TABLES
    tables = extract_table_refs(sql)
    if not tables:
        return False, []

    unknown = [t for t in tables if t not in allowed]
    return (len(unknown) == 0), unknown


# ---------
# Metric-friendly derived fields
# ---------

def derive_structural_fields(final_sql: str) -> Dict[str, Any]:
    """
    Returns fields you can log for reliability/security metrics.
    If REFUSE, fields are set safely.
    """
    out = (final_sql or "").strip()
    upper = out.upper()

    if upper.strip() == "REFUSE":
        return {
            "final_sql_hash": None,
            "sql_valid": False,
            "uses_only_allowed_tables": None,
            "unknown_table_refs": None,
        }

    uses_only_allowed, unknown = allowed_tables_check(out)

    return {
        "final_sql_hash": sql_hash(out),
        "sql_valid": sql_valid_select(out),
        "uses_only_allowed_tables": uses_only_allowed,
        "unknown_table_refs": unknown,
    }
