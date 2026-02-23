# policy/validators.py

class Refusal(Exception):
    def __init__(self, reason: str):
        self.reason = reason

def validate_intent(intent):
    if intent.metric not in {"creatinine"}:
        raise Refusal(
            f"Unsupported lab metric: {intent.metric}. "
            "Currently supported: creatinine."
        )

    if intent.time_window != "icu":
        raise Refusal("Unsupported time window")

    if intent.operation != "summary":
        raise Refusal("Unsupported operation")

    return intent
