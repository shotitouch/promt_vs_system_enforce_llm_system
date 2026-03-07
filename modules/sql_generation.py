from typing import Any, Dict

from llm.client import call_llm_raw
from llm.prompts.sql import (
    SQL_PROMPT_FINALITY,
    build_sql_after_discovery_prompt,
)
from utils.utils import clean_sql
from config import LONG_TOKEN_LIMIT


def _extract_measure_terms(intent: Dict[str, Any]) -> list[str]:
    lab_name = str(intent.get("lab_name", "") or "").strip().lower()
    if not lab_name:
        return []

    normalized = lab_name.replace("/", ",")
    normalized = normalized.replace(" and ", ",")
    parts = [p.strip() for p in normalized.split(",")]
    terms = [p for p in parts if p and p not in {"level", "levels", "value", "values"}]
    return terms[:5]


def _build_label_predicate(terms: list[str]) -> str:
    safe_terms = [t.replace("'", "\\'") for t in terms if t]
    if not safe_terms:
        return "FALSE"
    if len(safe_terms) == 1:
        return f"LOWER(dli.label) LIKE '%{safe_terms[0]}%'"
    return " OR ".join([f"LOWER(dli.label) LIKE '%{t}%'" for t in safe_terms])


def _template_discovery_lab_metadata(terms: list[str]) -> str:
    predicate = _build_label_predicate(terms)
    return f"""
SELECT
  le.itemid,
  LOWER(dli.label) AS lab_label,
  COUNT(*) AS icu_event_count
FROM `physionet-data.mimiciv_3_1_icu.icustays` icu
JOIN `physionet-data.mimiciv_3_1_hosp.labevents` le
  ON icu.subject_id = le.subject_id
 AND icu.hadm_id = le.hadm_id
JOIN `physionet-data.mimiciv_3_1_hosp.d_labitems` dli
  ON le.itemid = dli.itemid
WHERE le.valuenum IS NOT NULL
  AND le.charttime BETWEEN icu.intime AND icu.outtime
  AND ({predicate})
GROUP BY le.itemid, dli.label
ORDER BY icu_event_count DESC, le.itemid
LIMIT 20
""".strip()


def build_discovery_sql(intent: Dict[str, Any]) -> dict:
    """
    Deterministic discovery SQL selection.

    Returns:
      {"sql": str, "template_id": str, "source": "deterministic"}
    """
    terms = _extract_measure_terms(intent)
    if not terms:
        return {"sql": "SKIP", "template_id": "D_SKIP_NO_MEASURE", "source": "deterministic"}

    sql = _template_discovery_lab_metadata(terms)

    return {
        "sql": clean_sql(sql).strip(),
        "template_id": "D_LAB_METADATA_LOOKUP_V1",
        "source": "deterministic",
    }


def build_final_sql(
    question: str,
    discovery_context: str,
    intent_context: str | None = None,
) -> dict:
    prompt = build_sql_after_discovery_prompt(
        sql_prompt=SQL_PROMPT_FINALITY,
        discovery_context=discovery_context,
        question=question,
        intent_context=intent_context,
    )
    llm_result = call_llm_raw(prompt=prompt, max_tokens=LONG_TOKEN_LIMIT)
    sql = clean_sql(llm_result.get("content", "")).strip()
    return {"llm_result": llm_result, "sql": sql}


def format_rows_as_text(rows, max_rows: int = 50) -> str:
    if not rows:
        return "No discovery results returned."

    rows = rows[:max_rows]
    columns = list(rows[0].keys())
    if not columns:
        return "Discovery returned rows with no columns."

    header = " | ".join(columns)
    lines = [header]
    for r in rows:
        lines.append(" | ".join(str(r.get(col)) for col in columns))
    return "\n".join(lines)


# Backward compatibility
def run_discovery_sql_stage(intent: Dict[str, Any]) -> dict:
    return build_discovery_sql(intent=intent)


def run_final_sql_stage(
    question: str,
    discovery_context: str,
    intent_context: str | None = None,
) -> dict:
    return build_final_sql(
        question=question,
        discovery_context=discovery_context,
        intent_context=intent_context,
    )


def format_discovery_rows(rows, max_rows: int = 50) -> str:
    return format_rows_as_text(rows=rows, max_rows=max_rows)
