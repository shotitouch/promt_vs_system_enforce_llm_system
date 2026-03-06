# llm/client.py

from dotenv import load_dotenv
load_dotenv()
from config import DEFAULT_TOKEN_LIMIT, MODEL_NAME
from langchain_openai import ChatOpenAI
import time

# ---------------------------
# LLM Factory
# ---------------------------

def get_llm(max_tokens: int = DEFAULT_TOKEN_LIMIT):
    return ChatOpenAI(
        model=MODEL_NAME,
        temperature=0,
        max_tokens=max_tokens,
    )


# ---------------------------
# Raw Call (Adjustable)
# ---------------------------

def call_llm_raw(prompt: str, max_tokens: int = DEFAULT_TOKEN_LIMIT):
    llm = get_llm(max_tokens)

    start = time.perf_counter()
    response = llm.invoke(prompt)
    end = time.perf_counter()

    latency_ms = (end - start) * 1000

    prompt_tokens = None
    completion_tokens = None
    total_tokens = None

    if hasattr(response, "response_metadata"):
        usage = response.response_metadata.get("token_usage")
        if usage:
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")

    return {
        "content": response.content.strip(),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
        "model": MODEL_NAME,
        "max_tokens": max_tokens,
        "provider": "openai",
    }
