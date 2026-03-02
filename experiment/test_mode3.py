from modes.mode3 import mode3_answer
from experiment.benchmark_questions import BENCHMARK_QUESTIONS
from experiment.runner import run_experiment

MODE3_AUTHORITY = {
    "intent": "none",
    "sql_gen": "llm",
    "validation": "deterministic",
    "policy": "none",
    "aggregation": "none",
    "expression": "deterministic",
}


if __name__ == "__main__":

    run_experiment(
        mode_name="mode3",
        mode_fn=mode3_answer,
        questions=BENCHMARK_QUESTIONS,
        benchmark_category="in_scope",
        authority=MODE3_AUTHORITY,
        output_file="mode3_benchmark.jsonl",
        num_trials=1,
    )