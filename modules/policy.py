import time
from typing import Any, Dict, Optional

from llm.client import get_llm
from llm.prompts.policy import build_policy_prompt
from llm.schemas import PolicyDecision


def check_policy(question: str, intent_text: str, sql_text: str | None = None) -> dict:
    prompt = build_policy_prompt(question=question, intent_text=intent_text, sql_text=sql_text)
    llm = get_llm()
    structured_llm = llm.with_structured_output(PolicyDecision, include_raw=True)

    start = time.perf_counter()
    resp = structured_llm.invoke(prompt)
    end = time.perf_counter()

    latency_ms = (end - start) * 1000

    policy_obj = resp["parsed"]
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

    decision = policy_obj.decision
    scope_category = policy_obj.scope_category
    reason = policy_obj.reason
    violations = [str(v) for v in policy_obj.violations][:20]
    unsafe_request = policy_obj.unsafe_request

    # Policy-module enforcement: unsafe requests must refuse.
    if unsafe_request is True:
        decision = "refuse"
        if scope_category == "in_scope":
            scope_category = "unknown"
        if "unsafe_request" not in violations:
            violations.append("unsafe_request")
        if not reason:
            reason = "Request attempts to bypass constraints or requires unsupported assumptions."

    normalized_obj = PolicyDecision(
        decision=decision,
        reason=(reason or "")[:1000],
        scope_category=scope_category,
        violations=violations,
        unsafe_request=unsafe_request,
    )

    return {
        "llm_result": {
            "content": normalized_obj.model_dump_json(),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
        },
        "decision": normalized_obj.decision,
        "scope_category": normalized_obj.scope_category,
        "reason": normalized_obj.reason,
        "violations": normalized_obj.violations,
        "unsafe_request": normalized_obj.unsafe_request,
    }

def _collect_policy_violations(
    intent: Optional[Dict[str, Any]] = None,
) -> tuple[list[str], str]:
    intent = intent or {}
    violations: list[str] = []

    data_domain = intent.get("data_domain")
    if data_domain and data_domain != "lab":
        violations.append(f"unsupported_domain:{data_domain}")

    time_scope = intent.get("time_scope")
    if time_scope in {
        "hospital_period",
        "before_icu",
        "after_icu",
    }:
        violations.append(f"unsupported_time_scope:{time_scope}")

    scope_category = "out_of_scope" if violations else "in_scope"
    return violations, scope_category


def check_policy_deterministic(
    question: str,
    intent: Optional[Dict[str, Any]] = None,
    intent_text: str | None = None,
    sql_text: str | None = None,
) -> dict:
    violations, scope_category = _collect_policy_violations(
        intent=intent,
    )

    decision = "refuse" if violations else "allow"
    if violations:
        reason = "; ".join(violations[:5])
    else:
        reason = "within_supported_icu_lab_scope"

    raw_text = (
        f"deterministic_policy decision={decision} "
        f"scope_category={scope_category} "
        f"violations={violations}"
    )

    return {
        "decision": decision,
        "scope_category": scope_category,
        "reason": reason,
        "violations": violations[:20],
        "raw_text": raw_text[:1000],
        "intent_text": intent_text,
    }


# Backward compatibility
def run_policy_stage(question: str, intent_text: str, sql_text: str | None = None) -> dict:
    return check_policy(question=question, intent_text=intent_text, sql_text=sql_text)
