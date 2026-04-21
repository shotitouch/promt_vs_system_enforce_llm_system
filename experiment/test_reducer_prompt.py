import argparse
import json

from llm.contracts.reducer import ReductionPlan
from llm.prompts.reducer import build_reducer_planner_prompt
from modules.reducer_executor import execute_reduction_plan
from modules.reducer_hybrid import build_reducer_input_summary, plan_reduction_hybrid


SAMPLE_INTENT = {
    "intent_summary": "What is the average percentage change between the first and last creatinine values across all ICU stays?",
    "question_type": "summary",
    "data_domain": "lab",
    "lab_name": "creatinine",
    "time_scope": "icu_period",
    "result_scope": "cohort",
    "details": [
        "average percentage change",
        "first and last value per ICU stay",
    ],
    "notes": "Need first and last creatinine within each ICU stay, then percentage change, then average across stays.",
}


SAMPLE_ROWS = [
    {"stay_id": 1, "charttime": "2020-01-01 00:00:00", "valuenum": 1.0},
    {"stay_id": 1, "charttime": "2020-01-02 00:00:00", "valuenum": 1.2},
    {"stay_id": 2, "charttime": "2020-01-01 00:00:00", "valuenum": 0.8},
    {"stay_id": 2, "charttime": "2020-01-03 00:00:00", "valuenum": 1.0},
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect or run the hybrid reducer planner prompt."
    )
    parser.add_argument(
        "--prompt-only",
        action="store_true",
        help="Print the rendered reducer planner prompt without calling the model.",
    )
    args = parser.parse_args()

    reducer_input = build_reducer_input_summary(SAMPLE_ROWS)

    if args.prompt_only:
        prompt = build_reducer_planner_prompt(
            intent=SAMPLE_INTENT,
            reducer_input=reducer_input,
        )
        print(prompt)
        return

    result = plan_reduction_hybrid(intent=SAMPLE_INTENT, rows=SAMPLE_ROWS)
    print("Reducer input summary:")
    print(json.dumps(result["reducer_input"], indent=2, default=str))
    print("\nPlanner passed:")
    print(json.dumps(result["passed"], indent=2, default=str))
    print("\nPlan raw:")
    print(json.dumps(result["plan_raw_for_logging"], indent=2, default=str))
    print("\nPlan checker:")
    print(json.dumps(result["plan_check_trace"], indent=2, default=str))
    if not result["passed"]:
        print("\nPlanner error:")
        print(result["error"])
        print("\nLLM metadata:")
        print(json.dumps(result["llm_result"], indent=2, default=str))
        return

    plan = ReductionPlan.model_validate(result["plan"])
    execution = execute_reduction_plan(plan, SAMPLE_ROWS)
    print("\nExecuted reduction result:")
    print(json.dumps(execution, indent=2, default=str))
    print("\nLLM metadata:")
    print(json.dumps(result["llm_result"], indent=2, default=str))


if __name__ == "__main__":
    main()
