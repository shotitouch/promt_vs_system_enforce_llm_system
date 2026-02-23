import time
from typing import Dict, Any
from modes.types import ModeResult


def express_mode_result(mode_result: ModeResult, max_preview_rows: int = 5) -> Dict[str, Any]:
    """
    Deterministic output layer.
    No LLM.
    No interpretation.
    Just renders result shape.
    """

    start = time.perf_counter()

    if mode_result.refused:
        return {
            "answer_text": "REFUSE",
            "answer_format": "refuse",
            "expression_latency_ms": int((time.perf_counter() - start) * 1000)
        }

    if mode_result.final_error:
        return {
            "answer_text": f"ERROR: {mode_result.final_error}",
            "answer_format": "error",
            "expression_latency_ms": int((time.perf_counter() - start) * 1000)
        }

    if not mode_result.execution_success:
        return {
            "answer_text": "Execution failed.",
            "answer_format": "error",
            "expression_latency_ms": int((time.perf_counter() - start) * 1000)
        }

    if mode_result.final_row_count == 0:
        return {
            "answer_text": "No results found.",
            "answer_format": "empty",
            "expression_latency_ms": int((time.perf_counter() - start) * 1000)
        }

    rows = mode_result.final_rows_preview
    cols = mode_result.final_columns

    # Scalar result (1 row, 1 column)
    if len(rows) == 1 and len(cols) == 1:
        value = rows[0][cols[0]]
        return {
            "answer_text": str(value),
            "answer_format": "scalar",
            "expression_latency_ms": int((time.perf_counter() - start) * 1000)
        }

    # Table preview
    header = " | ".join(cols)
    lines = [header]
    for r in rows[:max_preview_rows]:
        lines.append(" | ".join(str(r.get(c)) for c in cols))

    return {
        "answer_text": "\n".join(lines),
        "answer_format": "table_preview",
        "expression_latency_ms": int((time.perf_counter() - start) * 1000)
    }