from experiment.benchmark_questions import BENCHMARK_QUESTIONS
from experiment.runner import run_experiment
from modes.system0 import system0_answer

SYSTEM0_AUTHORITY = {
    "sql_gen": "llm",
    "validation": "deterministic",
    "policy": "deterministic",
    "aggregation": "deterministic",
}


if __name__ == "__main__":

    run_experiment(
        mode_name="system0",
        mode_fn=system0_answer,
        questions=BENCHMARK_QUESTIONS,
        benchmark_category="in_scope",
        authority=SYSTEM0_AUTHORITY,
        output_file="system0_benchmark.jsonl",
        num_trials=5,
    )
