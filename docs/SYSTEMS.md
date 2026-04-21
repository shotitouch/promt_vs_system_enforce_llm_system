# SYSTEM Configurations

This file defines the current experiment system names after the request-gate
and artifact-validator boundary redesign.

The goal of the `S`-series is not to enumerate every possible combination.
Instead, it is to isolate the effect of authority variation at each critical
module while keeping the rest of the pipeline fixed.

## Fixed Pipeline (All Systems)

Question  
-> Intent (fixed)  
-> Request Gate  
-> Discovery SQL (fixed deterministic metadata lookup)  
-> Execute Discovery SQL  
-> SQL Generation Module / Final SQL  
-> Artifact Validation  
-> Execute Final SQL  
-> Reduction Execution (mandatory)  
-> Post Validation  
-> Renderer (fixed)

Notes:
- `Request Gate` functions as the request-level gate before SQL generation.
- `Artifact Validation` functions as the plan/output validator, including both pre-execution SQL checks and post-reduction output checks.
- `Reducer` functions as the numerical composition layer over returned rows.
- `Intent`, `Discovery`, `Execution`, and `Renderer` are fixed infrastructure.
- `S0` is the baseline. Other core systems vary one critical module at a time.

## Critical Modules and Allowed Authorities

- `sql_generation` (SQL generation module): `llm`, `hybrid`
- `request_gate` (request-level gate): `llm`, `deterministic`
- `artifact_validator` (plan/output validator): `llm`, `hybrid`, `deterministic`
- `reducer` (numerical composition layer): `hybrid`, `deterministic`

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

| System | Name | sql_generation | request_gate | artifact_validator | reducer | authority_score | Purpose | Status |
|---|---|---|---|---|---|---:|---|---|
| S0 | Baseline | llm | deterministic | deterministic | deterministic | 1.0 | Baseline for all isolated comparisons | Implemented |
| S1 | RequestGate-LLM | llm | llm | deterministic | deterministic | 2.0 | Isolates request-gate authority | Implemented |
| S2 | Reducer-Hybrid | llm | deterministic | deterministic | hybrid | 1.5 | Isolates reducer authority | Planned |
| S3 | Validator-LLM | llm | deterministic | llm | deterministic | 2.0 | Isolates LLM validation | Planned |
| S4 | Validator-Hybrid | llm | deterministic | hybrid | deterministic | 1.5 | Tests hybrid validation tradeoff | Planned |
| S5 | SQLGen-Hybrid | hybrid | deterministic | deterministic | deterministic | 0.5 | Isolates SQL-generation authority | Planned |

### Extended Comparison System

This system is not required for isolated module-effect analysis, but is useful
as a later production-oriented comparison point.

| System | Name | sql_generation | request_gate | artifact_validator | reducer | authority_score | Purpose | Status |
|---|---|---|---|---|---|---:|---|---|
| S6 | Safety-Stack | hybrid | llm | hybrid | deterministic | 2.0 | Combined higher-safety / higher-flexibility stack | Planned |

## Coverage Rationale

The core set covers the authority options currently under study:

- `request_gate`
  - deterministic: `S0`
  - llm: `S1`
- `artifact_validator`
  - deterministic: `S0`
  - llm: `S3`
  - hybrid: `S4`
- `sql_generation`
  - llm: `S0`
  - hybrid: `S5`
- `reducer`
  - deterministic: `S0`
  - hybrid: `S2`

This is sufficient for module-wise authority analysis without requiring a full
Cartesian product of all combinations.

## Reducer Scope Note

There is no separate fully LLM-driven reducer system in the current roadmap.

This is intentional. Reduction may need to operate over result sets that are too
large or too variable to pass directly through model context in a reliable way.
In this setting, a more realistic LLM role is to help specify or guide the
computation, while the computation itself is still executed by structured
non-LLM tools.

For that reason, reducer authority is currently defined as:
- deterministic
- hybrid

Rather than:
- deterministic
- llm

## Naming Guidance

- Use `SYSTEM X` for reports/charts/log grouping.
- Keep implementation labels aligned with system names (`system1`, etc.).
- If needed, add `system_name` into experiment records for direct grouping.
