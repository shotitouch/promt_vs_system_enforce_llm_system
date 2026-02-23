# llm/prompt_mode3.py

from llm.common import (
    EXPLANATION,
    PROMPT_LV_1,
    PROMPT_LV_2,
    OUTPUT_DISCOVERY
)

# -------------------------------------------------
# DISCOVERY PROMPT (Mode 3 only)
# -------------------------------------------------

MODE3_DISCOVERY_PROMPT = f"""
{EXPLANATION}

You are performing metadata discovery over MIMIC-IV.

Your task is to generate exactly ONE SELECT SQL query
to retrieve minimal relevant metadata needed to answer
the user's question.

Rules:
- Use only the provided tables.
- Use fully qualified table names with backticks.
- Include LIMIT 50.
- Return raw SQL only.
- Do NOT include markdown.
- Do NOT include explanations.
- If discovery is not required, output exactly: SKIP

{OUTPUT_DISCOVERY}
""".strip()

def build_mode3_discovery_prompt(question: str) -> str:
    return f"""
    {MODE3_DISCOVERY_PROMPT}

    ===== USER QUESTION =====
    {question}
    ===== END USER QUESTION =====
    """.strip()


# -------------------------------------------------
# FINAL QUERY PROMPT (Mode 3)
# -------------------------------------------------

def build_mode3_final_prompt(level: int, discovery_context: str, question: str) -> str:
    """
    Builds the final Mode 3 prompt by:
    - Selecting LV1 / LV2 governance level
    - Injecting discovery context
    - Appending the user question

    level: 1, 2, or 3
    discovery_context: text result from discovery stage
    question: original user question
    """

    if level == 1:
        base_prompt = PROMPT_LV_1
    elif level == 2:
        base_prompt = PROMPT_LV_2
    else:
        raise ValueError("Mode3 level must be 1, or 2")

    return f"""
    {base_prompt}

    ===== DISCOVERY RESULTS =====

    {discovery_context}

    ===== END DISCOVERY =====

    Use the discovery results above when helpful.
    Do NOT invent itemids or labels beyond the discovery results.

    If the question cannot be answered within ICU lab scope
    using the available information, output exactly: REFUSE.

    ===== USER QUESTION =====

    {question}

    ===== END USER QUESTION =====
    """.strip()
