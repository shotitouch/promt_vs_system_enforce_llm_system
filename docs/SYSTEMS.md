# SYSTEM Configurations

This file defines the current experiment system names after the policy/validation
boundary redesign.

The goal of the `S`-series is not to enumerate every possible combination.
Instead, it is to isolate the effect of authority variation at each critical
module while keeping the rest of the pipeline fixed.

## Fixed Pipeline (All Systems)

Question  
-> Intent (fixed)  
-> Policy Pre  
-> Discovery SQL (fixed deterministic metadata lookup)  
-> Execute Discovery SQL  
-> SQL Planner / Final SQL  
-> SQL Validation  
-> Execute Final SQL  
-> Aggregation Execution (mandatory)  
-> Post Validation  
-> Expression (fixed)

Notes:
- `Policy` functions as the request-level gate before planning.
- `Validation` functions as the plan/output validator, including both pre-execution SQL checks and post-aggregation output checks.
- `Aggregation` functions as the numerical composition layer over returned rows.
- `Intent`, `Discovery`, `Execution`, and `Expression` are fixed infrastructure.
- `S0` is the baseline. Other core systems vary one critical module at a time.

## Critical Modules and Allowed Authorities

- `sql_planner` (planner/sql module): `llm`, `hybrid`
- `policy` (request-level gate): `llm`, `deterministic`
- `validation` (plan/output validator): `llm`, `hybrid`, `deterministic`
- `aggregation` (numerical composition layer): `hybrid`, `deterministic`

## Authority Score

Authority score is computed over critical modules only:

- `llm` = `1.0`
- `hybrid` = `0.5`
- `deterministic` = `0.0`

`authority_score = sum(module_points)`

Max score with this setup is `3.5`.

## Canonical Systems (S-Series)

### Core Module-Variation Set

These systems are the main experiment set for measuring the effect of each
module's authority variation.

| System | Name | sql_planner | policy | validation | aggregation | authority_score | Purpose | Status |
|---|---|---|---|---|---|---:|---|---|
| S0 | Baseline | llm | deterministic | deterministic | deterministic | 1.0 | Baseline for all isolated comparisons | Implemented |
| S1 | Policy-LLM | llm | llm | deterministic | deterministic | 2.0 | Isolates policy authority | Implemented |
| S2 | Validation-LLM | llm | deterministic | llm | deterministic | 2.0 | Isolates LLM validation | Planned |
| S3 | Validation-Hybrid | llm | deterministic | hybrid | deterministic | 1.5 | Tests hybrid validation tradeoff | Planned |
| S4 | Planner-Hybrid | hybrid | deterministic | deterministic | deterministic | 0.5 | Isolates planner authority | Planned |
| S5 | Aggregation-Hybrid | llm | deterministic | deterministic | hybrid | 1.5 | Isolates aggregation authority | Planned |

### Extended Comparison System

This system is not required for isolated module-effect analysis, but is useful
as a later production-oriented comparison point.

| System | Name | sql_planner | policy | validation | aggregation | authority_score | Purpose | Status |
|---|---|---|---|---|---|---:|---|---|
| S6 | Safety-Stack | hybrid | llm | hybrid | deterministic | 2.0 | Combined higher-safety / higher-flexibility stack | Planned |

## Coverage Rationale

The core set covers the authority options currently under study:

- `policy`
  - deterministic: `S0`
  - llm: `S1`
- `validation`
  - deterministic: `S0`
  - llm: `S2`
  - hybrid: `S3`
- `sql_planner`
  - llm: `S0`
  - hybrid: `S4`
- `aggregation`
  - deterministic: `S0`
  - hybrid: `S5`

This is sufficient for module-wise authority analysis without requiring a full
Cartesian product of all combinations.

## Naming Guidance

- Use `SYSTEM X` for reports/charts/log grouping.
- Keep implementation labels aligned with system names (`system1`, etc.).
- If needed, add `system_name` into experiment records for direct grouping.
