# app.py
from fastapi import FastAPI
from modes.mode3 import mode3_answer

app = FastAPI()

@app.post("/ask")
def ask(payload: dict):
    question = payload.get("question")
    mode = payload.get("mode")

    if mode != "mode3":
        return {"error": "Only mode3 supported"}

    result = mode3_answer(question)
    return {
        "mode": "mode3",
        "answer_text": result.answer_text,
        "answer_format": result.answer_format,
        "execution_success": result.execution_success,
        "refused": result.refused,
        "final_error": result.final_error,
        "final_output": result.final_output,
    }
