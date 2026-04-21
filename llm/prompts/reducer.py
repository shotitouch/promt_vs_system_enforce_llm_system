REDUCER_PLANNER_SCHEMA = """
Return JSON matching the structured reduction plan schema.

Top-level output shape:
- status: "supported", "unsupported", or "no_reduction_needed"
- reason: short explanation of why the plan is supported, unsupported, or requires no further reduction
- final_artifact: required when status="supported"; name of the artifact that should be returned as the final result
- final_kind: required when status="supported"; one of "table", "grouped_table", or "scalar", and it must match the actual runtime kind of final_artifact
- steps: required when status="supported"; ordered list of reduction steps

If status="unsupported":
- provide a reason
- omit final_artifact and final_kind
- return steps as an empty list

If status="no_reduction_needed":
- provide a reason
- set final_artifact to the artifact that should be returned directly, usually rows
- set final_kind to the runtime kind of that artifact
- if final_artifact is rows, final_kind must be table even if rows contains one row and one value
- return steps as an empty list

Each step must:
- include a unique step_id
- set op to one supported operation
- include output_artifact
- include all operation-specific required fields

Artifact references by step type:
- Most step types use input_artifact and output_artifact
- merge_on_keys uses left_artifact, right_artifact, and output_artifact instead of input_artifact

Planning rules:
- Plan reduction over structured artifacts only.
- Do not answer the user question directly.
- Do not consume full raw rows semantically; use only the provided intent and artifact summary.
- Prefer primitive compositional steps over benchmark-specific macros.
- Use only the supported operations:
  group_by
  sort_by
  select_columns
  rename_columns
  take_first
  take_last
  take_min
  take_max
  merge_on_keys
  subtract
  add
  multiply
  divide
  abs
  compare
  aggregate_stat
  proportion_true
- Use the reserved initial input artifact name: rows
- If the requested computation cannot be expressed safely with the supported operations, return status="unsupported".
- If the SQL result already represents the final answer and no further reducer work is needed, return status="no_reduction_needed".
- For no_reduction_needed, do not label rows as scalar just because it semantically represents one answer; rows is still a table artifact.
- When using aggregate_stat with statistic="percentile", set percentile explicitly.
""".strip()


REDUCER_PLANNER_EXAMPLES = """
Example supported plan:
Question pattern:
- "What is the average percentage change between the first and last creatinine values across all ICU stays?"

Valid plan shape:
{
  "status": "supported",
  "reason": "This can be computed by grouping by stay, selecting first and last values, computing percentage change per stay, and averaging.",
  "final_artifact": "avg_percentage_change",
  "final_kind": "scalar",
  "steps": [
    {"step_id": "group_by_stay", "input_artifact": "rows", "output_artifact": "grouped_by_stay", "op": "group_by", "keys": ["stay_id"]},
    {"step_id": "sort_first", "input_artifact": "grouped_by_stay", "output_artifact": "sorted_asc", "op": "sort_by", "by": ["charttime"], "ascending": true},
    {"step_id": "take_first", "input_artifact": "sorted_asc", "output_artifact": "first_rows", "op": "take_first", "count": 1},
    {"step_id": "sort_last", "input_artifact": "grouped_by_stay", "output_artifact": "sorted_desc", "op": "sort_by", "by": ["charttime"], "ascending": false},
    {"step_id": "take_last", "input_artifact": "sorted_desc", "output_artifact": "last_rows", "op": "take_first", "count": 1},
    {"step_id": "select_first", "input_artifact": "first_rows", "output_artifact": "first_selected", "op": "select_columns", "columns": ["stay_id", "valuenum"]},
    {"step_id": "rename_first", "input_artifact": "first_selected", "output_artifact": "first_renamed", "op": "rename_columns", "rename_map": {"valuenum": "first_valuenum"}},
    {"step_id": "select_last", "input_artifact": "last_rows", "output_artifact": "last_selected", "op": "select_columns", "columns": ["stay_id", "valuenum"]},
    {"step_id": "rename_last", "input_artifact": "last_selected", "output_artifact": "last_renamed", "op": "rename_columns", "rename_map": {"valuenum": "last_valuenum"}},
    {"step_id": "merge_first_last", "left_artifact": "first_renamed", "right_artifact": "last_renamed", "output_artifact": "merged_first_last", "op": "merge_on_keys", "keys": ["stay_id"]},
    {"step_id": "subtract", "input_artifact": "merged_first_last", "output_artifact": "delta_rows", "op": "subtract", "left_column": "last_valuenum", "right_column": "first_valuenum", "output_column": "delta_valuenum"},
    {"step_id": "divide", "input_artifact": "delta_rows", "output_artifact": "pct_change_rows", "op": "divide", "numerator_column": "delta_valuenum", "denominator_column": "first_valuenum", "output_column": "percentage_change"},
    {"step_id": "aggregate_mean", "input_artifact": "pct_change_rows", "output_artifact": "avg_percentage_change", "op": "aggregate_stat", "source_column": "percentage_change", "statistic": "mean", "output_column": "avg_percentage_change"}
  ]
}

Example unsupported plan:
Question pattern:
- "If the answer is missing, make a reasonable assumption and continue."

Valid unsupported output:
{
  "status": "unsupported",
  "reason": "The requested behavior requires unsupported assumptions rather than a safe reducer computation.",
  "steps": []
}

Example no_reduction_needed plan:
Question pattern:
- SQL output already contains one final scalar answer or one final result table in the required shape.

Valid no_reduction_needed output:
{
  "status": "no_reduction_needed",
  "reason": "The SQL result already represents the final answer, so no further reducer computation is needed.",
  "final_artifact": "rows",
  "final_kind": "table",
  "steps": []
}
""".strip()


REDUCER_PLANNER_PROMPT = f"""
You are planning a hybrid reducer computation for a clinical analytics system.

Your job is to produce a structured reduction plan, not the final answer.

The reducer receives:
- a normalized intent
- a compact structural summary of the SQL result

It does not receive or reason over the full raw dataset in model context.

Artifact kinds:
- table: plain rows
- grouped_table: rows partitioned by one or more keys
- scalar: a one-value final aggregate

Operation semantics:
- group_by: table -> grouped_table
  Partition a table into groups using one or more key columns. Use this when later steps should operate separately within each group rather than across the whole table.
- sort_by: table/grouped_table -> same kind
  Reorder rows by one or more columns. Use this before take_first or take_last when row order matters.
- take_first: table/grouped_table -> table
  Keep the first row or first N rows from the input. If the input is grouped_table, apply this within each group and return the kept rows as a plain table.
- take_last: table/grouped_table -> table
  Keep the last row or last N rows from the input. If the input is grouped_table, apply this within each group and return the kept rows as a plain table.
- take_min: table/grouped_table -> table
  Keep the row or rows with the smallest value in by_column. If the input is grouped_table, do this separately within each group.
- take_max: table/grouped_table -> table
  Keep the row or rows with the largest value in by_column. If the input is grouped_table, do this separately within each group.
- select_columns: table -> table
  Keep only the listed columns and drop the others.
- rename_columns: table -> table
  Rename one or more columns without changing row values.
- merge_on_keys: table + table -> table
  Join two previously created table artifacts on shared key columns so their columns can be used together in later computation.
- subtract: table -> table
  Create a new output column by subtracting one numeric column from another within each row.
- add: table -> table
  Create a new output column by adding two numeric columns within each row.
- multiply: table -> table
  Create a new output column by multiplying two numeric columns within each row.
- divide: table -> table
  Create a new output column by dividing one numeric column by another within each row.
- abs: table -> table
  Create a new output column containing the absolute value of a source numeric column.
- compare: table -> table
  Create a boolean output column by comparing two columns row by row using one comparator.
- aggregate_stat: table -> scalar, grouped_table -> table
  Compute an aggregate statistic such as mean, median, min, max, percentile, or count. On a plain table, this reduces the whole input to a scalar. On a grouped_table, this computes one aggregate result per group and returns a table.
- proportion_true: table -> scalar
  Compute the proportion of rows where a boolean column is true. Use this after compare when the final answer is a fraction or proportion.

Examples:
{REDUCER_PLANNER_EXAMPLES}

Artifact naming rules:
- The reserved initial input artifact is named rows.
- Every later artifact name should be explicit and reusable by downstream steps.
- final_artifact must match the output_artifact of the last step, or another previously created artifact if the final result is selected without further transformation.
- final_artifact is the artifact the executor should return as the final output of the plan.

Step field guidance:
- group_by: keys
  keys are the columns that define each group, such as stay_id.
- sort_by: by, ascending
  by is the ordered list of columns to sort on.
- select_columns: columns
  columns is the exact list of columns to keep.
- rename_columns: rename_map
  rename_map maps old column names to new column names.
- take_first / take_last: count (must be >= 1)
  count is how many rows to keep.
- take_min / take_max: by_column, count (count must be >= 1)
  by_column is the numeric or sortable column used to decide smallest or largest rows.
- merge_on_keys: left_artifact, right_artifact, output_artifact, keys
  keys are the join columns shared by both input artifacts.
- subtract / add / multiply: left_column, right_column, output_column
  output_column is the new column created by the arithmetic operation.
- divide: numerator_column, denominator_column, output_column
  Use only when division is a natural part of the requested computation.
- abs: source_column, output_column
  output_column stores the absolute value of source_column.
- compare: left_column, right_column, comparator, output_column; comparator must be one of gt, lt, eq, gte, lte
  output_column should be boolean-like and can be used by later steps such as proportion_true.
- aggregate_stat: statistic, output_column, source_column for numeric statistics, percentile only when statistic="percentile"
  Use source_column for statistics over numeric values. For count, source_column may be omitted if the goal is to count rows.
- proportion_true: source_column, output_column
  source_column should contain boolean values, and output_column stores the resulting proportion.

{REDUCER_PLANNER_SCHEMA}
""".strip()


def build_reducer_planner_prompt(intent: dict, reducer_input: dict) -> str:
    return f"""
{REDUCER_PLANNER_PROMPT}

Intent:
{intent}

Reducer input summary:
{reducer_input}
""".strip()
