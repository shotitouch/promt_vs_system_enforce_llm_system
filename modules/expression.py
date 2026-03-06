from experiment.logging_schema import ExpressionTrace
from utils.expression import express_mode_result
from modes.types import ModeResult


def finalize_expression(result: ModeResult) -> ModeResult:
    expr = express_mode_result(result)
    result.answer_text = expr["answer_text"]
    result.answer_format = expr["answer_format"]
    result.expression_latency_ms = expr["expression_latency_ms"]
    result.expression_trace = ExpressionTrace(
        answer_format=result.answer_format,
        rendered_from_row_count=result.final_row_count,
    )
    return result

