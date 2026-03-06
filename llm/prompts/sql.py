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
- When using GROUP BY, every selected column must be included in GROUP BY
  or wrapped in an aggregate function.
- Do NOT mix GROUP BY and window functions in the same SELECT.
  Use subqueries or CTEs if both are required.
- Exclude NULL numeric values when performing calculations
  (`valuenum IS NOT NULL`).
- If using LIMIT also include ORDER BY.
- For median calculations prefer:
  APPROX_QUANTILES(valuenum, 100)[OFFSET(50)]

Additional Rules:
- Resolve lab tests by joining `d_labitems`.
- Do NOT guess itemid values.
- Match labels using LOWER(d_labitems.label).
""".strip()

GOAL_SQL_ONLY = """
Task:
Write a SQL query to answer the user's question.
Use fully-qualified table and field names.
Return only SQL.
""".strip()

OUTPUT_SQL_ONLY = """
Output format:
- Return raw SQL only
- Do NOT include markdown
- Do NOT include ```sql fences
- Do NOT include explanations or comments
""".strip()

SEMANTIC_FINALITY = """
Semantic finality requirement:

The SQL must compute the final answer entirely within SQL.

- Do NOT return raw event rows when aggregation is requested.
- If a single statistic is requested return a single-row result.
- If per ICU stay return one row per stay_id.
- All computation must occur in SQL.
""".strip()

OUTPUT_DISCOVERY = """
Output format:

Return either:
(A) raw SQL (single SELECT query)
OR
(B) exact token: SKIP

Rules:
- No markdown
- No explanations
""".strip()

DISCOVERY_PROMPT = f"""
{EXPLANATION}

You are performing metadata discovery over MIMIC-IV.

Generate ONE SQL query retrieving minimal metadata needed
to answer the question.

Rules:
- Use provided tables only
- Use fully-qualified names
- Include LIMIT <= 50 when returning rows

{OUTPUT_DISCOVERY}
""".strip()


def build_prompt(*rule_blocks: str) -> str:
    rules_text = "\n\n".join([b.strip() for b in rule_blocks if b and b.strip()])
    parts = [EXPLANATION]
    if rules_text:
        parts.append(rules_text)
    parts.append(GOAL_SQL_ONLY)
    parts.append(OUTPUT_SQL_ONLY)
    return "\n\n".join(parts).strip()


SQL_PROMPT = build_prompt()
SQL_PROMPT_FINALITY = build_prompt(SEMANTIC_FINALITY)


def build_discovery_prompt(question: str) -> str:
    return f"""
{DISCOVERY_PROMPT}

===== USER QUESTION =====
{question}
===== END USER QUESTION =====
""".strip()


def build_sql_after_discovery_prompt(
    sql_prompt: str,
    discovery_context: str,
    question: str,
    intent_context: str | None = None,
) -> str:
    intent_block = ""
    if intent_context:
        intent_block = f"""
===== INTENT ANALYSIS =====
{intent_context}
===== END INTENT ANALYSIS =====
"""

    return f"""
{sql_prompt}

{intent_block}

Use the discovery results below as context.

===== DISCOVERY RESULTS =====
{discovery_context}
===== END DISCOVERY RESULTS =====

===== USER QUESTION =====
{question}
===== END USER QUESTION =====
""".strip()

