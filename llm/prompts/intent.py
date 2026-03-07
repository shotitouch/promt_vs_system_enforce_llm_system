INTENT_SCHEMA = """
Output JSON with fields:

{
  "intent_summary": "...",
  "question_type": "...",
  "data_domain": "...",
  "lab_name": "...",
  "time_scope": "...",
  "result_scope": "...",
  "details": ["..."],
  "notes": "..."
}

Rules:
- JSON only
- No markdown
- No explanation
""".strip()

INTENT_PROMPT = f"""
You are interpreting a clinical analytics question.

Extract the analytical intent in structured form.

System scope:
ICU lab analytics only.

{INTENT_SCHEMA}
""".strip()


def build_intent_prompt(question: str) -> str:
    return f"""
{INTENT_PROMPT}

===== USER QUESTION =====
{question}
===== END USER QUESTION =====
""".strip()
