# app.py
from fastapi import FastAPI
from modes.system0 import system0_answer
from modes.system1 import system1_answer

app = FastAPI()

@app.post("/ask")
def ask(payload: dict):
    question = payload.get("question")
    mode = payload.get("mode")

    if mode == "system0":
        result = system0_answer(question)
        system_name = "system0"
    elif mode == "system1":
        result = system1_answer(question)
        system_name = "system1"
    else:
        return {"error": "Only system0 and system1 supported"}

    return {
        "system_name": system_name,
        "answer_text": result.answer_text,
        "answer_format": result.answer_format,
        "execution_success": result.execution_success,
        "refused": result.refused,
        "final_error": result.final_error,
        "final_sql": result.final_sql,
    }
