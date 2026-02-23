# modes/mode2.py
from llm.client import extract_intent
from policy.validators import validate_intent, Refusal
from policy.rules import LAB_ITEMIDS, MIN_POINTS
from schema.sql_templates import ICU_LAB_SUMMARY_SQL
from db.bigquery import run_template_query

def mode2_answer(question: str):
    try:
        # 1. Intent extraction (structure locked)
        intent = extract_intent(question)

        # 2. Semantic validation
        validate_intent(intent)

        # 3. Resolve lab metadata
        itemids = LAB_ITEMIDS[intent.metric]

        # 4. Execute SQL
        rows = run_template_query(ICU_LAB_SUMMARY_SQL, itemids)

        if not rows:
            raise Refusal("No data returned")

        result = rows[0]

        # 5. Evidence sufficiency
        if result["n_points"] < MIN_POINTS[intent.operation]:
            raise Refusal("Insufficient data")

        # 6. Deterministic answer
        return {
            "mode": "mode2",
            "metric": intent.metric,
            "time_window": intent.time_window,
            "operation": intent.operation,
            "result": result
        }

    except Refusal as r:
        return {
            "mode": "mode2",
            "status": "refused",
            "reason": r.reason
        }

    except Exception as e:
        return {
            "mode": "mode2",
            "status": "refused",
            "reason": f"Invalid intent extraction: {str(e)}"
        }
