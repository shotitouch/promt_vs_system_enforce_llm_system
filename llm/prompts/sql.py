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
- A single lab concept can map to multiple valid `itemid` values.
  Use discovery `lab_label` + `itemid` together: include all `itemid` values
  whose labels semantically match the requested lab concept, and exclude
  candidates with non-matching labels.
""".strip()

GOAL_SQL_ONLY = """
Task:
Write one SQL query that either:
1. directly answers the user's question when the computation is simple and naturally expressible in one SQL query, or
2. returns structured intermediate data for downstream reduction when the computation is multi-step, derived, temporal, or otherwise better handled by the reducer.

Decision rule:
1. First decide whether the question can be answered cleanly with one stable SQL layer.
2. Use direct final-answer SQL only when the result can be computed with a straightforward aggregate, filter, grouping, count, or ranking query without multi-step derived logic.
3. Use reducer-ready intermediate SQL when the question requires first/last comparisons, temporal ordering, per-stay derived metrics, ratios or percentage changes computed from intermediate values, conditional cohort summaries, or multiple logical computation stages.
4. When in doubt, prefer reducer-ready intermediate SQL over brittle multi-layer SQL.

The SQL is still part of answering the user's question even when it returns intermediate data for later reduction.
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
Aggregation handoff requirement:

When downstream reduction is the cleaner computation boundary, return reducer-ready intermediate data rather than a final derived scalar.

- Return rows, not narrative output.
- Preserve identifiers needed for grouping, especially `stay_id` when relevant.
- Preserve temporal columns such as `charttime` when first/last or ordering logic may be needed later.
- Preserve numeric value columns needed for downstream arithmetic.
- Do not collapse multi-step derived computations into a final scalar when reducer handoff is the cleaner boundary.
- Do not assume one itemid per lab concept; use discovery label/itemid context.
- Keep ICU time-window constraints and table restrictions enforced in SQL.
""".strip()

SQL_STRATEGY_EXAMPLES = """
Strategy examples:

Example A: direct final-answer SQL
- Question pattern: "What is the average creatinine value across all ICU stays?"
- Preferred SQL shape: a single SQL query that directly returns the final aggregate, because the computation is a straightforward aggregate.

Example B: reducer-ready intermediate SQL
- Question pattern: "What is the average percentage change between the first and last creatinine values across ICU stays?"
- Preferred SQL shape: rows that preserve the intermediate data needed for later reduction, such as `stay_id`, `charttime`, and `valuenum`, or equivalent per-stay endpoint rows.
- Do not force the full derived cohort metric into one brittle SQL layer when reducer handoff is cleaner.
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
    parts = [EXPLANATION, GOAL_SQL_ONLY]
    if rules_text:
        parts.append(rules_text)
    parts.append(OUTPUT_SQL_ONLY)
    return "\n\n".join(parts).strip()


SQL_PROMPT = build_prompt()
SQL_PROMPT_FINALITY = build_prompt(SEMANTIC_FINALITY, SQL_STRATEGY_EXAMPLES)


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
