from modes.mode3 import mode3_answer
from experiment.benchmark_questions import (
    IN_SCOPE_QUESTIONS,
    OUT_OF_SCOPE_QUESTIONS,
)
from experiment.runner import run_experiment


if __name__ == "__main__":

    run_experiment(
        mode_name="mode3",
        mode_fn=mode3_answer,
        questions=IN_SCOPE_QUESTIONS,
        levels=[1, 2],
        output_file="mode3_in_scope.jsonl",
        num_trials=1
    )

    run_experiment(
        mode_name="mode3",
        mode_fn=mode3_answer,
        questions=OUT_OF_SCOPE_QUESTIONS,
        levels=[1, 2],
        output_file="mode3_out_scope.jsonl",
        num_trials=1
    )