from modes.mode1 import mode1_answer

question = "Summarize creatinine levels during ICU stay."

for variant in ["A", "B", "C"]:
    print(f"\n===== Mode 1-{variant} =====")
    result = mode1_answer(question, variant)
    print(result)
