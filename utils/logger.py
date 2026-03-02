import json
from pathlib import Path
from datetime import date, datetime, time
from decimal import Decimal


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def _json_default(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def log_run(record: dict, filename: str = "experiment.jsonl"):
    path = LOG_DIR / filename

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=_json_default) + "\n")
