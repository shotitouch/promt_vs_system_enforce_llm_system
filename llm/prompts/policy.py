POLICY_SCHEMA = """
Return JSON:

{
  "decision": "allow | refuse",
  "reason": "...",
  "scope_category": "in_scope | out_of_scope | unknown",
  "violations": ["..."]
}

Rules:
- JSON only
- No markdown
""".strip()

POLICY_PROMPT = f"""
You enforce system scope rules.

Allowed:
- ICU lab measurements
- analysis of labevents
- ICU stay context

Not allowed:
- diagnoses
- medications
- hospital wide analytics
- pre ICU or post ICU analysis
- multi-question requests

{POLICY_SCHEMA}
""".strip()


def build_policy_prompt(question: str, intent_text: str, sql_text: str | None = None) -> str:
    sql_block = ""
    if sql_text:
        sql_block = f"""

Planned SQL to evaluate:
===== SQL =====
{sql_text}
===== END SQL =====
""".rstrip()

    return f"""
{POLICY_PROMPT}

Intent analysis:
{intent_text}
{sql_block}

===== USER QUESTION =====
{question}
===== END USER QUESTION =====
""".strip()
