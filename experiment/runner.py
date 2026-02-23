import time
import hashlib
from typing import Callable, List, Tuple

from experiment.logging_schema import ExperimentRecord
from utils.metrics import derive_structural_fields
from utils.logger import log_run


def run_experiment(
    mode_name: str,
    mode_fn: Callable,
    questions: List[Tuple[str, str, bool]],
    levels: List[int],
    output_file: str,
    num_trials: int = 1
):
    print(
        f"Start run experiment: {mode_name} | "
        f"output: {output_file} | num_trials: {num_trials}"
    )

    for qid, question, should_refuse in questions:

        for trial in range(1, num_trials + 1):

            for level in levels:

                full_mode_name = f"{mode_name}-LV{level}"
                total_start = time.perf_counter()

                record = ExperimentRecord(
                    mode=full_mode_name,
                    question_id=qid,
                    trial=trial,
                    question=question,
                    should_refuse=should_refuse,
                )

                # ----------------------------
                # 1️⃣ Run architecture
                # ----------------------------
                mode_result = mode_fn(question=question, level=level)

                # SQL trace
                record.sql_trace = mode_result.sql_trace

                # Execution state
                record.refused = mode_result.refused
                record.final_output = mode_result.final_output
                record.execution_success = mode_result.execution_success
                record.final_row_count = mode_result.final_row_count
                record.final_error = mode_result.final_error

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

                # ----------------------------
                # 2️⃣ Structural evaluation
                # ----------------------------
                if (
                    not record.refused
                    and record.final_output
                ):
                    structural = derive_structural_fields(record.final_output)
                    for k, v in structural.items():
                        setattr(record, k, v)

                    record.final_sql_hash = hashlib.md5(
                        record.final_output.encode()
                    ).hexdigest()

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