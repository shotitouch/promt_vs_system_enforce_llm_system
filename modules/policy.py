import json
from typing import Any, Dict, Optional

from llm.client import call_llm_raw
from llm.prompts.policy import build_policy_prompt


def _safe_parse_json(s: str) -> Optional[Dict[str, Any]]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except Exception:
                return None
        return None


def check_policy(question: str, intent_text: str, sql_text: str | None = None) -> dict:
    prompt = build_policy_prompt(question=question, intent_text=intent_text, sql_text=sql_text)
    llm_result = call_llm_raw(prompt=prompt)
    raw = (llm_result.get("content", "") or "").strip()
    payload = _safe_parse_json(raw)

    decision = None
    scope_category = None
    reason = None
    violations = []

    if isinstance(payload, dict):
        decision = payload.get("decision")
        scope_category = payload.get("scope_category")
        reason = payload.get("reason")
        violations = payload.get("violations") or []
    else:
        low = raw.lower()
        if "refuse" in low:
            decision = "refuse"
        elif "allow" in low:
            decision = "allow"
        else:
            decision = "none"
        scope_category = "unknown"
        reason = raw[:500]
        violations = []

    decision = (decision or "none").strip().lower()
    if decision not in ("allow", "refuse", "none"):
        decision = "none"

    if scope_category:
        scope_category = scope_category.strip().lower()
        if scope_category not in ("in_scope", "out_of_scope", "unknown"):
            scope_category = "unknown"
    else:
        scope_category = "unknown"

    if not isinstance(violations, list):
        violations = [str(violations)]

    return {
        "llm_result": llm_result,
        "decision": decision,
        "scope_category": scope_category,
        "reason": (reason or "")[:1000] if reason else None,
        "violations": [str(v) for v in violations][:20],
    }


# Backward compatibility
def run_policy_stage(question: str, intent_text: str, sql_text: str | None = None) -> dict:
    return check_policy(question=question, intent_text=intent_text, sql_text=sql_text)
