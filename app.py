# app.py
from fastapi import FastAPI
from modes.mode2 import mode2_answer

app = FastAPI()

@app.post("/ask")
def ask(payload: dict):
    question = payload.get("question")
    mode = payload.get("mode")

    if mode != "mode2":
        return {"error": "Only mode2 supported"}

    return mode2_answer(question)
