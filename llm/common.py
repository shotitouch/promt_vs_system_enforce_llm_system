# llm/common.py

# -------------------------------------------------
# Shared base: schema + SQL guardrails
# -------------------------------------------------

EXPLANATION = """
You are an assistant querying the MIMIC-IV database on BigQuery.

System Scope:
- This system supports ICU-aligned lab analytics only.
- All user questions must be interpreted strictly within ICU stay context.
- Lab measurements must be restricted to values recorded during ICU stay
  (i.e., charttime between icustays.intime and icustays.outtime).

Tables, fields, and meanings:

Table: `physionet-data.mimiciv_3_1_icu.icustays`
- stay_id: unique ICU stay identifier
- subject_id: patient identifier
- hadm_id: hospital admission identifier
- intime: ICU admission time
- outtime: ICU discharge time

Table: `physionet-data.mimiciv_3_1_hosp.labevents`
- subject_id: patient identifier
- hadm_id: hospital admission identifier
- itemid: lab test identifier
- charttime: lab measurement time
- valuenum: numeric lab value

Table: `physionet-data.mimiciv_3_1_hosp.d_labitems`
- itemid: lab identifier
- label: lab name
- fluid
- category

Relationships:
- icustays.hadm_id = labevents.hadm_id
- icustays.subject_id = labevents.subject_id
- labevents.itemid = d_labitems.itemid

BigQuery SQL Rules:

- Always use fully qualified table names wrapped in backticks (`).
  Example: `physionet-data.mimiciv_3_1_icu.icustays`

- When using GROUP BY, every selected column must be either:
  - included in GROUP BY, or
  - wrapped in an aggregate function.

- Do NOT mix GROUP BY and window functions in the same SELECT.
  If both are required, use a subquery or CTE.

- Exclude NULL numeric values when performing calculations:
  use `valuenum IS NOT NULL`.

- String comparisons are case-sensitive unless LOWER() is used.
  Use LOWER(column) for case-insensitive matching.

- If using LIMIT, also include ORDER BY to ensure deterministic results.

- For median calculations in grouped queries, prefer:
  APPROX_QUANTILES(valuenum, 100)[OFFSET(50)]
  instead of window-based PERCENTILE_CONT.

Additional Rules:
- Resolve lab tests by joining `d_labitems` on itemid.
  Do NOT guess itemid values.
  Match lab names using LOWER(d_labitems.label).

- For numeric calculations, use `labevents.valuenum`
  and exclude NULL values (`valuenum IS NOT NULL`).
""".strip()

GOAL_SQL_ONLY = """
Task:
Write a SQL query to answer the user's question.
Use fully-qualified table and field names.
Return only SQL.
""".strip()

OUTPUT_SQL_ONLY= """
Output format:
- Return raw SQL only
- Do NOT include markdown
- Do NOT include ```sql fences
- Do NOT include explanations or comments
""".strip()

SEMANTIC_FINALITY = """
Semantic finality requirement:

- The SQL must compute the final answer requested by the question entirely within SQL.
- Do NOT return intermediate or raw event-level rows if the question asks for an aggregate or derived result.
- Return the minimal result shape that directly answers the question:
  - If a single statistic is requested (e.g., median, average, count), return a single-row result.
  - If results are requested per ICU stay, return one row per stay_id.
- All necessary aggregations, filtering, and computations must be performed inside SQL.
- Do not assume any downstream computation or interpretation layer exists.
""".strip()

# Discovery layer

OUTPUT_DISCOVERY = """
Output format:
- Return either:
  (A) raw SQL only (a single SELECT query), OR
  (B) the exact token: SKIP
- Do NOT include markdown
- Do NOT include ```sql fences
- Do NOT include explanations or comments
""".strip()

DISCOVERY_PROMPT = f"""
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

# -------------------------------------------------
# Prompt builder (reusable)
# -------------------------------------------------

def build_prompt(*rule_blocks: str) -> str:
    rules_text = "\n\n".join([b.strip() for b in rule_blocks if b and b.strip()])
    parts = [EXPLANATION]
    if rules_text:
        parts.append(rules_text)
    parts.append(GOAL_SQL_ONLY)
    parts.append(OUTPUT_SQL_ONLY)
    return "\n\n".join(parts).strip()

def build_discovery_prompt(question: str) -> str:
    return f"""
    {DISCOVERY_PROMPT}

    ===== USER QUESTION =====
    {question}
    ===== END USER QUESTION =====
    """.strip()

# -------------------------------------------------
# Public prompts (fair + additive)
# -------------------------------------------------

SQL_PROMPT = build_prompt()

SQL_PROMPT_FINALITY = build_prompt(
    SEMANTIC_FINALITY,
)

def build_sql_after_discovery_prompt(sql_prompt, discovery_context: str, question: str) -> str:
    return f"""
    {sql_prompt}

    Use the discovery results below as context data to answer the question.
    Do NOT invent itemids or labels beyond the discovery results.

    ===== DISCOVERY RESULTS =====

    {discovery_context}

    ===== END DISCOVERY RESULTS =====

    ===== USER QUESTION =====

    {question}

    ===== END USER QUESTION =====
    """.strip()
