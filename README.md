# Authority Allocation in Hybrid LLM Systems

This project studies reliability in a modular clinical analytics pipeline over
MIMIC-IV ICU lab data.  
The focus is authority allocation across critical modules in a hybrid LLM
system.

In documentation, the module meanings are:
- `policy`: request-level gate
- `validation`: plan/output validator
- `aggregation`: numerical composition layer

## Current Systems

- Implemented systems:
  - `system0`: baseline
  - `system1`: policy-LLM variant
- Critical module authority:
  - `system0`
    - `sql_gen`: `llm`
    - `policy`: `deterministic`
    - `validation`: `deterministic`
    - `aggregation`: `deterministic` (mandatory)
- `system1`
  - `sql_gen`: `llm`
  - `policy`: `llm`
  - `validation`: `deterministic`
  - `aggregation`: `deterministic` (mandatory)

Canonical system definitions are documented in
[`docs/SYSTEMS.md`](docs/SYSTEMS.md).

## Pipeline

`Question -> Intent -> Policy Pre -> Discovery SQL -> Discovery Execute -> Final SQL -> SQL Validation -> Final SQL Execute -> Aggregation -> Post Validation -> Expression`

- Intent: LLM structured output
- Discovery: deterministic metadata lookup
- Planner / Final SQL: LLM
- Policy: request-level gate
- Validation: deterministic plan/output validator with SQL checks before execution and output checks after aggregation
- Aggregation: deterministic numerical composition over returned rows
- Expression: deterministic formatting only

## Repository Structure

- `modes/system0.py`: System0 orchestration pipeline
- `modes/system1.py`: System1 orchestration pipeline
- `modules/`: reusable module implementations
- `llm/prompts/`: prompt templates
- `llm/contracts/`: structured output contracts
- `experiment/`: benchmark questions, runner, logging schema, test entrypoint
- `db/`: BigQuery execution helpers
- `logs/`: experiment JSONL outputs

## Scope

This repository is written as a research architecture project, not as a
general-purpose package.

Primary focus:

- controlled authority-allocation experiments
- module-level traceability
- reliability and safety behavior under fixed benchmark settings

## Reproducibility Reference

Reference experiment entrypoint:

`python -m experiment.test_system1`

Baseline experiment entrypoint:

`python -m experiment.test_system0`

## Logging

Main record schema is in `experiment/logging_schema.py`.

Notable fields include:

- Identity: `system_name`, `question_id`, `trial`, `question`
- Traces: `intent_trace`, `policy_pre_trace`, `discovery_*`,
  `validation_trace`, `post_validation_trace`, `aggregation_trace`, `expression_trace`
- SQL/outputs: `final_sql`, `final_sql_hash`, `output_hash`,
  `aggregation_output_hash`
- Cost/latency: LLM stage metrics, DB latency, end-to-end latency

## Notes

- Deterministic aggregation currently has bounded capability by design.
- Some benchmark items can fail with `failure_stage="aggregation"` if operation
  is outside deterministic support.
- This is intentional for measuring coverage vs reliability tradeoffs.
