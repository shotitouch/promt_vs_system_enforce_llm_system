from llm.client import call_llm_raw
from llm.prompts.sql import (
    SQL_PROMPT_FINALITY,
    build_discovery_prompt,
    build_sql_after_discovery_prompt,
)
from utils.utils import clean_sql
from config import LONG_TOKEN_LIMIT


def run_discovery_sql_stage(question: str) -> dict:
    prompt = build_discovery_prompt(question=question)
    llm_result = call_llm_raw(prompt=prompt)
    sql = clean_sql(llm_result.get("content", "")).strip()
    return {"llm_result": llm_result, "sql": sql}


def run_final_sql_stage(
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


def format_discovery_rows(rows, max_rows: int = 50) -> str:
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
