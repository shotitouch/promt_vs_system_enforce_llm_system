from experiment.benchmark_questions import BENCHMARK_QUESTIONS
from experiment.runner import run_experiment
from modes.system2 import system2_answer

SYSTEM2_AUTHORITY = {
    "sql_gen": "llm",
    "validation": "deterministic",
    "policy": "deterministic",
    "aggregation": "hybrid",
}


if __name__ == "__main__":

    run_experiment(
        mode_name="system2",
        mode_fn=system2_answer,
        questions=BENCHMARK_QUESTIONS,
        benchmark_category="in_scope",
        authority=SYSTEM2_AUTHORITY,
        output_file="system2_benchmark.jsonl",
        num_trials=5,
    )
