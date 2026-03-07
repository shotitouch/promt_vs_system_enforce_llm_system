# SYSTEM Configurations

This file defines experiment system names using the canonical `S0..S7` design.

## Fixed Pipeline (All Systems)

Question  
-> Intent (fixed)  
-> Policy Pre  
-> Discovery SQL (fixed deterministic metadata lookup)  
-> Execute Discovery SQL  
-> SQL Planner / Final SQL  
-> Policy Post  
-> SQL Validation  
-> Execute Final SQL  
-> Aggregation Execution (mandatory)  
-> Expression (fixed)

Notes:
- `Policy` includes both pre and post checkpoints and counts as one module.
- `Intent`, `Discovery`, `Execution`, and `Expression` are fixed infrastructure.

## Critical Modules and Allowed Authorities

- `sql_planner` (planner/sql module): `llm`, `hybrid`
- `policy`: `llm`, `deterministic`
- `validation`: `llm`, `hybrid`, `deterministic`
- `aggregation`: `hybrid`, `deterministic`

## Authority Score

Authority score is computed over critical modules only:

- `llm` = `1.0`
- `hybrid` = `0.5`
- `deterministic` = `0.0`

`authority_score = sum(module_points)`

Max score with this setup is `3.5`.

## Canonical Systems (S-Series)

| System | Name | sql_planner | policy | validation | aggregation | authority_score | Status |
|---|---|---|---|---|---|---:|---|
| S0 | Baseline | llm | deterministic | deterministic | deterministic | 1.0 | Planned baseline target |
| S1 | Policy-LLM | llm | llm | deterministic | deterministic | 2.0 | Current System 1 behavior |
| S2 | Validation-LLM | llm | deterministic | llm | deterministic | 2.0 | Planned |
| S3 | Validation-Hybrid | llm | deterministic | hybrid | deterministic | 1.5 | Planned |
| S4 | Planner-Hybrid | hybrid | deterministic | deterministic | deterministic | 0.5 | Planned |
| S5 | Aggregation-Hybrid | llm | deterministic | deterministic | hybrid | 1.5 | Planned |
| S6 | Safety-Stack | hybrid | deterministic | hybrid | deterministic | 1.0 | Planned |
| S7 | LLM-Heavy | llm | llm | llm | hybrid | 3.5 | Planned |

## Naming Guidance

- Use `SYSTEM X` for reports/charts/log grouping.
- Keep implementation labels aligned with system names (`system1`, etc.).
- If needed, add `system_name` into experiment records for direct grouping.
