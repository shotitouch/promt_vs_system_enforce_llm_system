from modes.common import run_mode
from modes.types import ModeResult


def system1_answer(question: str) -> ModeResult:
    """
    System 1:
    - policy: llm
    - reducer: deterministic
    """
    return run_mode(
        question=question,
        policy_mode="llm",
        reducer_mode="deterministic",
    )
