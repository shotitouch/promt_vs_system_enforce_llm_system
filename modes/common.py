from experiment.logging_schema import LLMStageMetric
from modes.types import ModeResult


def add_llm_usage(result: ModeResult, llm_result: dict, stage: str, latency_ms: int) -> None:
    prompt_tokens = llm_result.get("prompt_tokens", 0) or 0
    completion_tokens = llm_result.get("completion_tokens", 0) or 0
    total_tokens = llm_result.get("total_tokens", 0) or 0

    result.llm_call_count += 1
    result.llm_total_prompt_tokens += prompt_tokens
    result.llm_total_completion_tokens += completion_tokens
    result.llm_total_tokens += total_tokens
    result.llm_total_latency_ms += latency_ms

    result.llm_stage_metrics.append(
        LLMStageMetric(
            stage=stage,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )
    )
