import json
from pathlib import Path


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def log_run(record: dict, filename: str = "experiment.jsonl"):
    path = LOG_DIR / filename

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")