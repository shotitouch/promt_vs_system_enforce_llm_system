import json
from pathlib import Path
import pandas as pd

LOG_PATH = Path("logs/mode3_runs.jsonl")  # change if you have a unified log file later


def load_jsonl(path: Path) -> pd.DataFrame:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return pd.DataFrame(rows)


def safe_div(a, b):
    return (a / b) if b else None


def compute_mode_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes per-mode metrics:
    - Refusal precision/recall (requires should_refuse)
    - Exec success rate
    - SQL validity rate (among non-refused)
    - Scope violation rates (among non-refused)
    - Schema violation rate (among non-refused, ignoring None)
    - Determinism (avg % most-common hash per question)
    - Cost (avg tokens, latency)
    """
    out_rows = []

    # Ensure columns exist
    for col in [
        "mode", "question_id", "trial", "should_refuse",
        "refused", "execution_success", "sql_valid",
        "has_icu_window", "has_icustays_join",
        "uses_only_allowed_tables", "final_sql_hash",
        "llm_total_tokens", "llm_total_latency_ms",
        "db_total_latency_ms", "total_latency_ms",
        "final_error"
    ]:
        if col not in df.columns:
            df[col] = None

    modes = sorted(df["mode"].dropna().unique().tolist())

    for m in modes:
        d = df[df["mode"] == m].copy()

        total = len(d)
        refused = int(d["refused"].fillna(False).sum())
        non_refused = d[~d["refused"].fillna(False)]
        non_refused_n = len(non_refused)

        exec_success = int(d["execution_success"].fillna(False).sum())
        exec_success_rate = safe_div(exec_success, total)

        # SQL validity among non-refused
        sql_valid_n = int(non_refused["sql_valid"].fillna(False).sum())
        sql_valid_rate = safe_div(sql_valid_n, non_refused_n)

        # Scope / join compliance among non-refused (treat None as unknown, exclude)
        def rate_true(series: pd.Series):
            s = series.dropna()
            return safe_div(int(s.sum()), len(s))

        icu_window_rate = rate_true(non_refused["has_icu_window"])
        join_rate = rate_true(non_refused["has_icustays_join"])

        # Schema compliance among non-refused (exclude None)
        schema_ok_rate = rate_true(non_refused["uses_only_allowed_tables"])

        # Refusal precision/recall (only if should_refuse exists)
        # correct_refusal = refused AND should_refuse
        should_refuse_known = d["should_refuse"].dropna()
        if len(should_refuse_known) == 0:
            refuse_precision = None
            refuse_recall = None
        else:
            d_sr = d.dropna(subset=["should_refuse"]).copy()
            d_sr["should_refuse"] = d_sr["should_refuse"].astype(bool)
            d_sr["refused"] = d_sr["refused"].fillna(False).astype(bool)

            correct_refusals = int((d_sr["refused"] & d_sr["should_refuse"]).sum())
            total_refusals = int(d_sr["refused"].sum())
            total_should_refuse = int(d_sr["should_refuse"].sum())

            refuse_precision = safe_div(correct_refusals, total_refusals)
            refuse_recall = safe_div(correct_refusals, total_should_refuse)

        # Determinism: for each question_id, compute fraction of runs that match the most common hash
        # (exclude refused and missing hashes)
        det_scores = []
        det_base = non_refused.dropna(subset=["question_id", "final_sql_hash"])
        if len(det_base) > 0:
            for qid, g in det_base.groupby("question_id"):
                counts = g["final_sql_hash"].value_counts()
                top = int(counts.iloc[0])
                det_scores.append(top / len(g))
            determinism_avg = sum(det_scores) / len(det_scores) if det_scores else None
        else:
            determinism_avg = None

        # Cost averages
        avg_tokens = d["llm_total_tokens"].dropna().astype(float).mean() if d["llm_total_tokens"].notna().any() else None
        avg_llm_ms = d["llm_total_latency_ms"].dropna().astype(float).mean() if d["llm_total_latency_ms"].notna().any() else None
        avg_db_ms = d["db_total_latency_ms"].dropna().astype(float).mean() if d["db_total_latency_ms"].notna().any() else None
        avg_total_ms = d["total_latency_ms"].dropna().astype(float).mean() if d["total_latency_ms"].notna().any() else None

        # Error rate
        error_rate = safe_div(int(d["final_error"].notna().sum()), total)

        out_rows.append({
            "mode": m,
            "n": total,

            "exec_success_rate": exec_success_rate,
            "error_rate": error_rate,

            "refusal_rate": safe_div(refused, total),
            "refusal_precision": refuse_precision,
            "refusal_recall": refuse_recall,

            "sql_valid_rate_non_refused": sql_valid_rate,
            "icu_window_rate_non_refused": icu_window_rate,
            "join_rate_non_refused": join_rate,
            "schema_ok_rate_non_refused": schema_ok_rate,

            "determinism_avg_by_question": determinism_avg,

            "avg_llm_tokens": avg_tokens,
            "avg_llm_latency_ms": avg_llm_ms,
            "avg_db_latency_ms": avg_db_ms,
            "avg_total_latency_ms": avg_total_ms,
        })

    return pd.DataFrame(out_rows)


def compute_question_determinism(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per (mode, question_id): determinism and key counts.
    """
    base = df.copy()
    base["refused"] = base["refused"].fillna(False).astype(bool)

    base = base[~base["refused"]].dropna(subset=["mode", "question_id", "final_sql_hash"])
    rows = []

    for (mode, qid), g in base.groupby(["mode", "question_id"]):
        vc = g["final_sql_hash"].value_counts()
        top_hash = vc.index[0]
        top_count = int(vc.iloc[0])
        total = len(g)
        determinism = top_count / total if total else None

        rows.append({
            "mode": mode,
            "question_id": qid,
            "runs": total,
            "unique_hashes": int(vc.shape[0]),
            "top_hash": top_hash,
            "top_count": top_count,
            "determinism": determinism,
        })

    return pd.DataFrame(rows).sort_values(["mode", "question_id"])


def main():
    if not LOG_PATH.exists():
        raise FileNotFoundError(f"Log file not found: {LOG_PATH}")

    df = load_jsonl(LOG_PATH)

    # Show quick sanity info
    print(f"Loaded {len(df)} rows from {LOG_PATH}")
    if "mode" in df.columns:
        print("Modes:", sorted(df["mode"].dropna().unique().tolist()))

    mode_summary = compute_mode_summary(df)
    q_det = compute_question_determinism(df)

    # Pretty print
    pd.set_option("display.max_columns", 200)
    pd.set_option("display.width", 160)

    print("\n=== MODE SUMMARY ===")
    print(mode_summary)

    print("\n=== PER-QUESTION DETERMINISM (mode, question_id) ===")
    print(q_det)

    # Optional exports
    out_dir = Path("logs/analysis")
    out_dir.mkdir(parents=True, exist_ok=True)

    mode_summary.to_csv(out_dir / "mode_summary.csv", index=False)
    q_det.to_csv(out_dir / "question_determinism.csv", index=False)

    print(f"\nSaved CSVs to: {out_dir}")


if __name__ == "__main__":
    main()