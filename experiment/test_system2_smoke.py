from experiment.benchmark_questions import BENCHMARK_QUESTIONS
from experiment.runner import run_experiment
from modes.system2 import system2_answer

SYSTEM2_AUTHORITY = {
    "sql_gen": "llm",
    "validation": "deterministic",
    "policy": "deterministic",
    "aggregation": "hybrid",
}

SMOKE_QUESTION_IDS = {
    "S1",  # simple in-scope SQL aggregate
    "G1",  # reducer-sensitive derived metric
    "V3",  # validation-sensitive question
    "P1",  # refusal / policy case
}

SMOKE_QUESTIONS = [
    question
    for question in BENCHMARK_QUESTIONS
    if question["question_id"] in SMOKE_QUESTION_IDS
]


if __name__ == "__main__":

    run_experiment(
        mode_name="system2-smoke",
        mode_fn=system2_answer,
        questions=SMOKE_QUESTIONS,
        benchmark_category="in_scope",
        authority=SYSTEM2_AUTHORITY,
        output_file="system2_smoke_benchmark.jsonl",
        num_trials=2,
    )
