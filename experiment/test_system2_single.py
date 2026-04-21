import json

from modes.system2 import system2_answer


QUESTION_ID = "G1"
QUESTION = "What is the average percentage change between the first and last creatinine values across all ICU stays?"


if __name__ == "__main__":
    result = system2_answer(QUESTION)
    print(f"Question ID: {QUESTION_ID}")
    print(json.dumps(result.model_dump(), indent=2, default=str))
