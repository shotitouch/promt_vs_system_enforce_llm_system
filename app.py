# app.py
from fastapi import FastAPI
from modes.system1 import system1_answer

app = FastAPI()

@app.post("/ask")
def ask(payload: dict):
    question = payload.get("question")
    mode = payload.get("mode")

    if mode != "system1":
        return {"error": "Only system1 supported"}

    result = system1_answer(question)
    return {
        "system_name": "system1",
        "answer_text": result.answer_text,
        "answer_format": result.answer_format,
        "execution_success": result.execution_success,
        "refused": result.refused,
        "final_error": result.final_error,
        "final_sql": result.final_sql,
    }
