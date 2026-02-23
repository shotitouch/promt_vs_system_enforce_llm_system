# db/bigquery.py
from google.cloud import bigquery

client = bigquery.Client()


# -------------------------------------------------
# MODE 2 — Deterministic template execution
# -------------------------------------------------
def run_template_query(sql: str, itemids: list[int]):
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter(
                "itemids", "INT64", itemids
            )
        ]
    )
    job = client.query(sql, job_config=job_config)
    return [dict(row) for row in job.result()]


# -------------------------------------------------
# MODE 1 & MODE 3 — Raw SQL execution
# -------------------------------------------------
def run_raw_query(sql: str):
    job = client.query(sql)
    return [dict(row) for row in job.result()]
