from modes.system1 import system1_answer
from experiment.benchmark_questions import BENCHMARK_QUESTIONS
from experiment.runner import run_experiment

SYSTEM1_AUTHORITY = {
    "sql_gen": "llm",
    "validation": "deterministic",
    "policy": "llm",
    "aggregation": "deterministic",
}


if __name__ == "__main__":

    run_experiment(
        mode_name="system1",
        mode_fn=system1_answer,
        questions=BENCHMARK_QUESTIONS,
        benchmark_category="in_scope",
        authority=SYSTEM1_AUTHORITY,
        output_file="system1_benchmark.jsonl",
        num_trials=1,
    )
