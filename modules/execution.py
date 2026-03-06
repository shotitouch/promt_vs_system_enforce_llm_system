import time

from db.bigquery import run_raw_query


class DBExecutionError(RuntimeError):
    def __init__(self, message: str, latency_ms: int):
        super().__init__(message)
        self.latency_ms = latency_ms


def execute_sql(sql: str) -> dict:
    start = time.perf_counter()
    try:
        rows = run_raw_query(sql)
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        raise DBExecutionError(str(e), latency_ms) from e
    end = time.perf_counter()
    return {
        "rows": rows,
        "latency_ms": int((end - start) * 1000),
    }
