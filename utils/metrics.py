# utils/metrics.py

import hashlib
import re
from typing import List, Tuple, Dict, Any, Optional

# Allowed tables in this project (update later if you add demographics)
ALLOWED_TABLES = {
    "physionet-data.mimiciv_3_1_icu.icustays",
    "physionet-data.mimiciv_3_1_hosp.labevents",
    "physionet-data.mimiciv_3_1_hosp.d_labitems",
}

# ---------
# SQL normalize + hash (for stability)
# ---------

def normalize_sql(sql: str) -> str:
    """Lightweight normalization for stable hashing."""
    s = (sql or "").strip()
    s = re.sub(r"\s+", " ", s)           # collapse whitespace
    s = s.replace("`", "")               # ignore backticks for hashing
    s = s.lower()
    return s

def sql_hash(sql: str) -> str:
    """Short stable hash for comparing across trials."""
    norm = normalize_sql(sql)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]


# ---------
# Structural checks (scope + anchoring)
# ---------

def has_icu_window(sql: str) -> bool:
    """
    Checks for ICU time window constraint presence.
    We look for a pattern like:
      labevents.charttime BETWEEN icustays.intime AND icustays.outtime
    allowing minor whitespace/case variations.
    """
    s = normalize_sql(sql)
    return (
        "between" in s and
        "intime" in s and
        "outtime" in s and
        "charttime" in s
    )

def has_icustays_join(sql: str) -> bool:
    """
    Checks for join anchoring between icustays and labevents on subject_id and hadm_id.
    This is heuristic (string-based), but good enough for CS800.
    """
    s = normalize_sql(sql)
    if "icustays" not in s or "labevents" not in s:
        return False

    return (
        "subject_id" in s and
        "hadm_id" in s
    )


# ---------
# Allowed table detection (schema violation / hallucination)
# ---------

_TABLE_REF_RE = re.compile(r"`([^`]+)`")  # captures backticked table refs

def extract_backticked_refs(sql: str) -> List[str]:
    """Extracts all backticked identifiers. We treat those containing dataset.table as table refs."""
    return _TABLE_REF_RE.findall(sql or "")

def extract_table_refs(sql: str) -> List[str]:
    """
    Returns table refs of the form: physionet-data.mimiciv_3_1_xxx.yyy
    from backticks.
    """
    refs = extract_backticked_refs(sql)
    tables = []
    for r in refs:
        # keep only likely full table refs (dataset.schema.table)
        if r.count(".") >= 2:
            tables.append(r)
    return tables

def allowed_tables_check(sql: str, allowed: Optional[set] = None) -> Tuple[bool, List[str]]:
    """
    Checks if all referenced tables (from backticks) are within allowed set.
    If SQL doesn’t use backticks, this will under-detect; encourage backticks via prompt rules.
    """
    allowed = allowed or ALLOWED_TABLES
    tables = extract_table_refs(sql)
    unknown = [t for t in tables if t not in allowed]
    # If tables list is empty, we cannot assert it's safe; mark as False to be conservative.
    if not tables:
        return None, []
    return (len(unknown) == 0), unknown


# ---------
# SQL validity flag (based on your existing guard)
# ---------

def sql_valid_select(sql: str) -> bool:
    s = (sql or "").strip().lower()
    return s.startswith("select")


# ---------
# Metric-friendly derived fields
# ---------

def derive_structural_fields(final_output: str) -> Dict[str, Any]:
    """
    Returns fields you can log for reliability/security metrics.
    If REFUSE, fields are set safely.
    """
    out = (final_output or "").strip()
    upper = out.upper()

    if upper.strip() == "REFUSE":
        return {
            "final_sql_hash": None,
            "sql_valid": False,
            "has_icu_window": None,
            "has_icustays_join": None,
            "uses_only_allowed_tables": None,
            "unknown_table_refs": None,
        }

    uses_only_allowed, unknown = allowed_tables_check(out)

    return {
        "final_sql_hash": sql_hash(out),
        "sql_valid": sql_valid_select(out),
        "has_icu_window": has_icu_window(out),
        "has_icustays_join": has_icustays_join(out),
        "uses_only_allowed_tables": uses_only_allowed,
        "unknown_table_refs": unknown,
    }
