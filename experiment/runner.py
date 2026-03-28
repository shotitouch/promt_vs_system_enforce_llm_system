import time
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from experiment.logging_schema import ExperimentRecord, ValidationTrace
from utils.metrics import derive_structural_fields
from utils.logger import log_run


def run_experiment(
    mode_name: str,
    mode_fn: Callable,
    questions: List[Any],
    benchmark_category: Optional[str],
    authority: Dict[str, str],
    output_file: str,
    num_trials: int = 1,
    levels: Optional[List[int]] = None,
):
    print(
        f"Start run experiment: {mode_name} | "
        f"output: {output_file} | num_trials: {num_trials}"
    )

    for question_item in questions:
        if isinstance(question_item, dict):
            qid = question_item["question_id"]
            question = question_item["question"]
            should_refuse = question_item["should_refuse"]
            question_benchmark_category = question_item["benchmark_category"]
            question_primary_module = question_item.get("primary_module")
            attribution_confidence = question_item.get("attribution_confidence")
        else:
            qid, question, should_refuse = question_item
            question_benchmark_category = benchmark_category
            question_primary_module = None
            attribution_confidence = None

        level_values = levels or [None]

        for trial in range(1, num_trials + 1):

            for level in level_values:

                full_mode_name = (
                    f"{mode_name}-LV{level}" if level is not None else mode_name
                )
                total_start = time.perf_counter()

                record = ExperimentRecord(
                    system_name=full_mode_name,
                    question_id=qid,
                    trial=trial,
                    question=question,
                    benchmark_category=question_benchmark_category,
                    should_refuse=should_refuse,
                    authority=authority,
                )
                record.primary_module = question_primary_module
                if attribution_confidence:
                    record.authority_notes = f"attribution_confidence={attribution_confidence}"

                # ----------------------------
                # 1️⃣ Run architecture
                # ----------------------------
                if level is None:
                    mode_result = mode_fn(question=question)
                else:
                    mode_result = mode_fn(question=question, level=level)

                # SQL trace
                record.sql_trace = mode_result.sql_trace
                record.discovery_source = mode_result.discovery_source
                record.discovery_template_id = mode_result.discovery_template_id
                record.intent_trace = mode_result.intent_trace
                record.validation_trace = mode_result.validation_trace
                record.discovery_validation_trace = mode_result.discovery_validation_trace
                record.final_validation_trace = mode_result.final_validation_trace
                record.post_validation_trace = mode_result.post_validation_trace
                record.policy_trace = mode_result.policy_trace
                record.policy_pre_trace = mode_result.policy_pre_trace
                record.discovery_execution_trace = mode_result.discovery_execution_trace
                record.aggregation_trace = mode_result.aggregation_trace
                record.aggregation_plan_raw = mode_result.aggregation_plan_raw
                record.aggregation_output_preview = mode_result.aggregation_output_preview
                record.expression_trace = mode_result.expression_trace

                # Execution state
                record.refused = mode_result.refused
                record.refusal_source = mode_result.refusal_source
                record.final_sql = mode_result.final_sql
                record.execution_success = mode_result.execution_success
                record.final_row_count = mode_result.final_row_count
                record.final_error = mode_result.final_error
                record.failure_stage = mode_result.failure_stage
                record.db_error = mode_result.db_error
                record.final_rows_preview = mode_result.final_rows_preview
                record.final_columns = mode_result.final_columns

                # ----------------------------
                # Cost metrics (LLM totals)
                # ----------------------------
                record.llm_call_count = mode_result.llm_call_count
                record.llm_total_prompt_tokens = mode_result.llm_total_prompt_tokens
                record.llm_total_completion_tokens = mode_result.llm_total_completion_tokens
                record.llm_total_tokens = mode_result.llm_total_tokens
                record.llm_total_latency_ms = int(mode_result.llm_total_latency_ms)

                # ✅ NEW: per-layer LLM metrics
                record.llm_stage_metrics = mode_result.llm_stage_metrics

                # DB cost
                record.db_call_count = mode_result.db_call_count
                record.db_total_latency_ms = int(mode_result.db_total_latency_ms)

                # Expression layer
                record.answer_text = mode_result.answer_text
                record.answer_format = mode_result.answer_format
                record.expression_latency_ms = mode_result.expression_latency_ms
                record.output_hash = (
                    hashlib.md5(record.answer_text.encode()).hexdigest()
                    if record.answer_text
                    else None
                )
                record.aggregation_output_hash = (
                    hashlib.md5(
                        json.dumps(
                            record.aggregation_output_preview,
                            sort_keys=True,
                            default=str,
                        ).encode("utf-8")
                    ).hexdigest()
                    if record.aggregation_output_preview
                    else None
                )
                record.policy_compliant = (record.refused == should_refuse)

                # ----------------------------
                # 2️⃣ Structural evaluation
                # ----------------------------
                if (
                    not record.refused
                    and record.final_sql
                ):
                    structural = derive_structural_fields(record.final_sql)
                    record.final_sql_hash = structural["final_sql_hash"]

                    if record.validation_trace is None:
                        failures = []
                        if structural["sql_valid"] is False:
                            failures.append("invalid_sql")
                        if structural["uses_only_allowed_tables"] is False:
                            failures.append("unauthorized_table")
                        if structural["has_icustays_join"] is False:
                            failures.append("missing_required_join")
                        if structural["has_icu_window"] is False:
                            failures.append("missing_required_window_constraint")

                        record.validation_trace = ValidationTrace(
                            passed=(len(failures) == 0),
                            checked_rules=[
                                "sql_valid",
                                "uses_only_allowed_tables",
                                "has_required_joins",
                                "has_required_window_constraints",
                            ],
                            failures=failures,
                            sql_valid=structural["sql_valid"],
                            uses_only_allowed_tables=structural["uses_only_allowed_tables"],
                            unknown_table_refs=structural["unknown_table_refs"] or [],
                            has_required_joins=structural["has_icustays_join"],
                            has_required_window_constraints=structural["has_icu_window"],
                        )

                # ----------------------------
                # 3️⃣ End-to-end timing
                # ----------------------------
                record.total_latency_ms = int(
                    (time.perf_counter() - total_start) * 1000
                )

                # ----------------------------
                # 4️⃣ Log
                # ----------------------------
                log_run(record.model_dump(), filename=output_file)

    print("Run finished")
