# mode2/mode1.py
from llm.client import call_llm_raw
from llm.prompt_mode1 import (
    MODE1_A_PROMPT,
    MODE1_B_PROMPT,
    MODE1_C_PROMPT,
)
from db.bigquery import run_raw_query
from utils.utils import strip_sql_fences

PROMPTS = {
    "A": MODE1_A_PROMPT,
    "B": MODE1_B_PROMPT,
    "C": MODE1_C_PROMPT,
}

def mode1_answer(question: str, variant: str = "A"):
    prompt = PROMPTS[variant]

    sql = call_llm_raw(
        prompt=prompt,
        question=question,
    )["content"]
    print('SQL:')
    print(sql)
    sql = strip_sql_fences(sql)
    # Minimal guard (security hygiene, NOT policy)
    if not sql.lower().strip().startswith("select"):
        return {
            "mode": f"mode1-{variant}",
            "error": "Non-SELECT SQL generated",
            "raw_output": sql,
        }

    try:
        rows = run_raw_query(sql)
        return {
            "mode": f"mode1-{variant}",
            "sql": sql,
            "rows": rows,
        }
    except Exception as e:
        return {
            "mode": f"mode1-{variant}",
            "sql": sql,
            "error": str(e),
        }
