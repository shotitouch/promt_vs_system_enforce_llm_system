import time

from llm.client import get_llm
from llm.schemas import System1Intent
from llm.prompts.intent import build_intent_prompt


def extract_intent(question: str) -> dict:
    prompt = build_intent_prompt(question=question)
    llm = get_llm()
    structured_llm = llm.with_structured_output(System1Intent, include_raw=True)

    start = time.perf_counter()
    resp = structured_llm.invoke(prompt)
    end = time.perf_counter()

    latency_ms = (end - start) * 1000

    intent_obj = resp["parsed"]
    raw_msg = resp["raw"]

    prompt_tokens = None
    completion_tokens = None
    total_tokens = None

    if hasattr(raw_msg, "response_metadata"):
        usage = raw_msg.response_metadata.get("token_usage")
        if usage:
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")

    return {
        "content": intent_obj.model_dump_json(),
        "intent": intent_obj.model_dump(),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
    }


# Backward compatibility
def run_intent_stage(question: str) -> dict:
    return extract_intent(question)
