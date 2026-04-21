from modes.common import run_mode
from modes.types import ModeResult


def system2_answer(question: str) -> ModeResult:
    """
    System 2:
    - policy: deterministic
    - reducer: hybrid
    """
    return run_mode(
        question=question,
        policy_mode="deterministic",
        reducer_mode="hybrid",
    )
