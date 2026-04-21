from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from llm.contracts.reducer import (
    AbsStep,
    AddStep,
    AggregateStatStep,
    CompareStep,
    DivideStep,
    GroupByStep,
    MergeOnKeysStep,
    MultiplyStep,
    ProportionTrueStep,
    ReductionPlan,
    RenameColumnsStep,
    SelectColumnsStep,
    SortByStep,
    SubtractStep,
    TakeFirstStep,
    TakeLastStep,
    TakeMaxStep,
    TakeMinStep,
)


class ReducerExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        step_id: str | None = None,
        op: str | None = None,
        artifact: str | None = None,
    ):
        self.step_id = step_id
        self.op = op
        self.artifact = artifact
        detail = message
        if step_id or op or artifact:
            detail = (
                f"{message}; step_id={step_id!r}; op={op!r}; artifact={artifact!r}"
            )
        super().__init__(detail)


@dataclass
class RuntimeArtifact:
    kind: str  # "table" | "grouped_table" | "scalar"
    rows: List[Dict[str, Any]]
    columns: List[str]
    group_keys: List[str]


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _column_order(rows: List[Dict[str, Any]]) -> List[str]:
    return list(rows[0].keys()) if rows else []


def _make_table(rows: List[Dict[str, Any]]) -> RuntimeArtifact:
    return RuntimeArtifact(
        kind="table",
        rows=rows,
        columns=_column_order(rows),
        group_keys=[],
    )


def _make_table_with_columns(
    rows: List[Dict[str, Any]],
    columns: List[str],
) -> RuntimeArtifact:
    return RuntimeArtifact(
        kind="table",
        rows=rows,
        columns=list(columns),
        group_keys=[],
    )


def _make_grouped_table(
    rows: List[Dict[str, Any]], group_keys: List[str]
) -> RuntimeArtifact:
    return RuntimeArtifact(
        kind="grouped_table",
        rows=rows,
        columns=_column_order(rows),
        group_keys=group_keys,
    )


def _make_grouped_table_with_columns(
    rows: List[Dict[str, Any]],
    columns: List[str],
    group_keys: List[str],
) -> RuntimeArtifact:
    return RuntimeArtifact(
        kind="grouped_table",
        rows=rows,
        columns=list(columns),
        group_keys=list(group_keys),
    )


def _make_scalar(output_column: str, value: Any) -> RuntimeArtifact:
    rows = [{output_column: value}]
    return RuntimeArtifact(
        kind="scalar",
        rows=rows,
        columns=[output_column],
        group_keys=[],
    )


def _require_kind(
    op_name: str,
    src: RuntimeArtifact,
    allowed_kinds: set[str],
) -> None:
    if src.kind not in allowed_kinds:
        allowed = ",".join(sorted(allowed_kinds))
        raise ReducerExecutionError(
            f"{op_name}_requires_kind:{allowed};got:{src.kind}"
        )


def _group_rows(
    rows: List[Dict[str, Any]], keys: List[str]
) -> Dict[Tuple[Any, ...], List[Dict[str, Any]]]:
    buckets: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for row in rows:
        key = tuple(row.get(k) for k in keys)
        buckets.setdefault(key, []).append(row)
    return buckets


def _sort_key(row: Dict[str, Any], by: List[str]) -> Tuple[Any, ...]:
    return tuple(row.get(col) for col in by)


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "t", "yes", "y", "1"}:
            return True
        if lowered in {"false", "f", "no", "n", "0"}:
            return False
    return None


def _sortable_value(value: Any) -> tuple[int, Any]:
    if value is None:
        return (3, "")

    if isinstance(value, bool):
        return (1, int(value))

    num = _to_float(value)
    if num is not None:
        return (0, num)

    return (2, str(value))


def _compare_pair(left: Any, right: Any, comparator: str) -> bool | None:
    if left is None or right is None:
        return None

    left_num = _to_float(left)
    right_num = _to_float(right)

    if left_num is not None and right_num is not None:
        a, b = left_num, right_num
    elif comparator == "eq":
        a, b = left, right
    elif isinstance(left, str) and isinstance(right, str):
        a, b = left, right
    else:
        raise ValueError(
            f"compare_incompatible_types:left={type(left).__name__},right={type(right).__name__}"
        )

    if comparator == "gt":
        return a > b
    if comparator == "lt":
        return a < b
    if comparator == "eq":
        return a == b
    if comparator == "gte":
        return a >= b
    if comparator == "lte":
        return a <= b

    raise ValueError(f"unsupported_comparator:{comparator}")


def _append_output_column(columns: List[str], output_column: str) -> List[str]:
    out_columns = list(columns)
    if output_column not in out_columns:
        out_columns.append(output_column)
    return out_columns


def _pick_min_rows(
    rows: List[Dict[str, Any]],
    by_column: str,
    count: int,
) -> List[Dict[str, Any]]:
    candidates = [row for row in rows if row.get(by_column) is not None]
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda r: _sortable_value(r.get(by_column)))
    return ordered[:count]


def _pick_max_rows(
    rows: List[Dict[str, Any]],
    by_column: str,
    count: int,
) -> List[Dict[str, Any]]:
    candidates = [row for row in rows if row.get(by_column) is not None]
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda r: _sortable_value(r.get(by_column)))
    return list(reversed(ordered[-count:]))


def _exec_group_by(step: GroupByStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("group_by", src, {"table"})
    return _make_grouped_table_with_columns(
        rows=list(src.rows),
        columns=src.columns,
        group_keys=step.keys,
    )


def _exec_sort_by(step: SortByStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("sort_by", src, {"table", "grouped_table"})
    if src.kind == "table":
        rows = sorted(
            src.rows,
            key=lambda r: _sort_key(r, step.by),
            reverse=not step.ascending,
        )
        return _make_table_with_columns(rows, src.columns)

    buckets = _group_rows(src.rows, src.group_keys)
    out_rows: List[Dict[str, Any]] = []
    for _, group in buckets.items():
        out_rows.extend(
            sorted(
                group,
                key=lambda r: _sort_key(r, step.by),
                reverse=not step.ascending,
            )
        )
    return _make_grouped_table_with_columns(out_rows, src.columns, src.group_keys)


def _exec_take_first(step: TakeFirstStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("take_first", src, {"table", "grouped_table"})
    if src.kind == "table":
        return _make_table_with_columns(src.rows[: step.count], src.columns)

    buckets = _group_rows(src.rows, src.group_keys)
    out_rows: List[Dict[str, Any]] = []
    for _, group in buckets.items():
        out_rows.extend(group[: step.count])
    return _make_table_with_columns(out_rows, src.columns)


def _exec_take_last(step: TakeLastStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("take_last", src, {"table", "grouped_table"})
    if src.kind == "table":
        return _make_table_with_columns(src.rows[-step.count :], src.columns)

    buckets = _group_rows(src.rows, src.group_keys)
    out_rows: List[Dict[str, Any]] = []
    for _, group in buckets.items():
        out_rows.extend(group[-step.count :])
    return _make_table_with_columns(out_rows, src.columns)


def _exec_take_min(step: TakeMinStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("take_min", src, {"table", "grouped_table"})

    if src.kind == "table":
        return _make_table_with_columns(
            _pick_min_rows(src.rows, step.by_column, step.count),
            src.columns,
        )

    buckets = _group_rows(src.rows, src.group_keys)
    out_rows: List[Dict[str, Any]] = []
    for _, group in buckets.items():
        out_rows.extend(_pick_min_rows(group, step.by_column, step.count))
    return _make_table_with_columns(out_rows, src.columns)


def _exec_take_max(step: TakeMaxStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("take_max", src, {"table", "grouped_table"})

    if src.kind == "table":
        return _make_table_with_columns(
            _pick_max_rows(src.rows, step.by_column, step.count),
            src.columns,
        )

    buckets = _group_rows(src.rows, src.group_keys)
    out_rows: List[Dict[str, Any]] = []
    for _, group in buckets.items():
        out_rows.extend(_pick_max_rows(group, step.by_column, step.count))
    return _make_table_with_columns(out_rows, src.columns)


def _exec_select_columns(step: SelectColumnsStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("select_columns", src, {"table"})
    rows = [{col: row.get(col) for col in step.columns} for row in src.rows]
    return _make_table_with_columns(rows, step.columns)


def _exec_rename_columns(step: RenameColumnsStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("rename_columns", src, {"table"})
    rows: List[Dict[str, Any]] = []
    for row in src.rows:
        new_row: Dict[str, Any] = {}
        for key, value in row.items():
            new_row[step.rename_map.get(key, key)] = value
        rows.append(new_row)
    new_columns = [step.rename_map.get(key, key) for key in src.columns]
    return _make_table_with_columns(rows, new_columns)


def _exec_merge_on_keys(
    step: MergeOnKeysStep, left: RuntimeArtifact, right: RuntimeArtifact
) -> RuntimeArtifact:
    _require_kind("merge_on_keys_left", left, {"table"})
    _require_kind("merge_on_keys_right", right, {"table"})
    right_index: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for row in right.rows:
        key = tuple(row.get(k) for k in step.keys)
        right_index.setdefault(key, []).append(row)

    out_rows: List[Dict[str, Any]] = []
    for left_row in left.rows:
        key = tuple(left_row.get(k) for k in step.keys)
        matches = right_index.get(key, [])
        for right_row in matches:
            merged = dict(left_row)
            for col, value in right_row.items():
                if col not in merged:
                    merged[col] = value
            out_rows.append(merged)

    merged_columns = list(left.columns)
    for col in right.columns:
        if col not in merged_columns:
            merged_columns.append(col)
    return _make_table_with_columns(out_rows, merged_columns)


def _exec_subtract(step: SubtractStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("subtract", src, {"table"})
    out_rows: List[Dict[str, Any]] = []
    for row in src.rows:
        left = _to_float(row.get(step.left_column))
        right = _to_float(row.get(step.right_column))
        out = dict(row)
        out[step.output_column] = None if left is None or right is None else left - right
        out_rows.append(out)
    return _make_table_with_columns(
        out_rows,
        _append_output_column(src.columns, step.output_column),
    )


def _exec_add(step: AddStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("add", src, {"table"})
    out_rows: List[Dict[str, Any]] = []
    for row in src.rows:
        left = _to_float(row.get(step.left_column))
        right = _to_float(row.get(step.right_column))
        out = dict(row)
        out[step.output_column] = None if left is None or right is None else left + right
        out_rows.append(out)
    return _make_table_with_columns(
        out_rows,
        _append_output_column(src.columns, step.output_column),
    )


def _exec_multiply(step: MultiplyStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("multiply", src, {"table"})
    out_rows: List[Dict[str, Any]] = []
    for row in src.rows:
        left = _to_float(row.get(step.left_column))
        right = _to_float(row.get(step.right_column))
        out = dict(row)
        out[step.output_column] = None if left is None or right is None else left * right
        out_rows.append(out)
    return _make_table_with_columns(
        out_rows,
        _append_output_column(src.columns, step.output_column),
    )


def _exec_divide(step: DivideStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("divide", src, {"table"})
    out_rows: List[Dict[str, Any]] = []
    for row in src.rows:
        num = _to_float(row.get(step.numerator_column))
        den = _to_float(row.get(step.denominator_column))
        if num is None or den is None:
            value = None
        elif den == 0:
            raise ValueError("divide_by_zero_in_reducer_plan")
        else:
            value = num / den

        out = dict(row)
        out[step.output_column] = value
        out_rows.append(out)
    return _make_table_with_columns(
        out_rows,
        _append_output_column(src.columns, step.output_column),
    )


def _exec_abs(step: AbsStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("abs", src, {"table"})
    out_rows: List[Dict[str, Any]] = []
    for row in src.rows:
        value = _to_float(row.get(step.source_column))
        out = dict(row)
        out[step.output_column] = None if value is None else abs(value)
        out_rows.append(out)
    return _make_table_with_columns(
        out_rows,
        _append_output_column(src.columns, step.output_column),
    )


def _exec_compare(step: CompareStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("compare", src, {"table"})
    out_rows: List[Dict[str, Any]] = []
    for row in src.rows:
        out = dict(row)
        out[step.output_column] = _compare_pair(
            row.get(step.left_column),
            row.get(step.right_column),
            step.comparator,
        )
        out_rows.append(out)
    return _make_table_with_columns(
        out_rows,
        _append_output_column(src.columns, step.output_column),
    )


def _aggregate_values(
    values: List[float], statistic: str, percentile: float | None
) -> float | int:
    if statistic == "mean":
        return sum(values) / len(values)
    if statistic == "median":
        return statistics.median(values)
    if statistic == "min":
        return min(values)
    if statistic == "max":
        return max(values)
    if statistic == "count":
        return len(values)
    if statistic == "percentile":
        if percentile is None:
            raise ValueError("percentile_required")
        ordered = sorted(values)
        idx = int(round((percentile / 100.0) * (len(ordered) - 1)))
        return ordered[idx]
    raise ValueError(f"unsupported_statistic:{statistic}")


def _exec_aggregate_stat(step: AggregateStatStep, src: RuntimeArtifact) -> RuntimeArtifact:
    _require_kind("aggregate_stat", src, {"table", "grouped_table"})
    if src.kind == "table":
        if step.statistic == "count" and step.source_column is None:
            return _make_scalar(step.output_column, len(src.rows))

        values = [_to_float(row.get(step.source_column)) for row in src.rows]
        usable = [v for v in values if v is not None]
        if not usable:
            raise ValueError("no_usable_values_for_aggregate_stat")

        return _make_scalar(
            step.output_column,
            _aggregate_values(usable, step.statistic, step.percentile),
        )

    buckets = _group_rows(src.rows, src.group_keys)
    out_rows: List[Dict[str, Any]] = []
    for key_tuple, group in buckets.items():
        if step.statistic == "count" and step.source_column is None:
            agg_value = len(group)
        else:
            values = [_to_float(row.get(step.source_column)) for row in group]
            usable = [v for v in values if v is not None]
            if not usable:
                raise ValueError("no_usable_values_for_grouped_aggregate_stat")
            agg_value = _aggregate_values(usable, step.statistic, step.percentile)

        row = {k: v for k, v in zip(src.group_keys, key_tuple)}
        row[step.output_column] = agg_value
        out_rows.append(row)

    out_columns = list(src.group_keys)
    if step.output_column not in out_columns:
        out_columns.append(step.output_column)
    return _make_table_with_columns(out_rows, out_columns)


def _exec_proportion_true(
    step: ProportionTrueStep,
    src: RuntimeArtifact,
) -> RuntimeArtifact:
    _require_kind("proportion_true", src, {"table"})
    bools = [_to_bool(row.get(step.source_column)) for row in src.rows]
    usable = [b for b in bools if b is not None]
    if not usable:
        raise ValueError("no_usable_boolean_values_for_proportion_true")
    proportion = sum(1 for b in usable if b) / len(usable)
    return _make_scalar(step.output_column, proportion)


def execute_reduction_plan(
    plan: ReductionPlan,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if plan.status == "unsupported":
        raise ReducerExecutionError(f"unsupported_reduction_plan:{plan.reason}")

    artifacts: Dict[str, RuntimeArtifact] = {
        "rows": _make_table(rows),
    }

    if plan.status == "no_reduction_needed":
        final_artifact = artifacts[plan.final_artifact]
        return {
            "kind": final_artifact.kind,
            "rows": final_artifact.rows,
            "columns": final_artifact.columns,
            "artifacts": {
                name: {
                    "kind": art.kind,
                    "columns": art.columns,
                    "row_count": len(art.rows),
                }
                for name, art in artifacts.items()
            },
        }

    for step in plan.steps:
        try:
            if isinstance(step, GroupByStep):
                artifacts[step.output_artifact] = _exec_group_by(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, SortByStep):
                artifacts[step.output_artifact] = _exec_sort_by(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, TakeFirstStep):
                artifacts[step.output_artifact] = _exec_take_first(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, TakeLastStep):
                artifacts[step.output_artifact] = _exec_take_last(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, TakeMinStep):
                artifacts[step.output_artifact] = _exec_take_min(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, TakeMaxStep):
                artifacts[step.output_artifact] = _exec_take_max(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, SelectColumnsStep):
                artifacts[step.output_artifact] = _exec_select_columns(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, RenameColumnsStep):
                artifacts[step.output_artifact] = _exec_rename_columns(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, MergeOnKeysStep):
                artifacts[step.output_artifact] = _exec_merge_on_keys(
                    step,
                    artifacts[step.left_artifact],
                    artifacts[step.right_artifact],
                )

            elif isinstance(step, SubtractStep):
                artifacts[step.output_artifact] = _exec_subtract(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, AddStep):
                artifacts[step.output_artifact] = _exec_add(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, MultiplyStep):
                artifacts[step.output_artifact] = _exec_multiply(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, DivideStep):
                artifacts[step.output_artifact] = _exec_divide(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, AbsStep):
                artifacts[step.output_artifact] = _exec_abs(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, CompareStep):
                artifacts[step.output_artifact] = _exec_compare(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, AggregateStatStep):
                artifacts[step.output_artifact] = _exec_aggregate_stat(
                    step, artifacts[step.input_artifact]
                )

            elif isinstance(step, ProportionTrueStep):
                artifacts[step.output_artifact] = _exec_proportion_true(
                    step, artifacts[step.input_artifact]
                )

            else:
                raise ReducerExecutionError(
                    f"operation_not_implemented:{type(step).__name__}"
                )
        except ReducerExecutionError as e:
            raise ReducerExecutionError(
                str(e),
                step_id=step.step_id,
                op=getattr(step, "op", None),
                artifact=getattr(step, "input_artifact", None),
            ) from e
        except KeyError as e:
            raise ReducerExecutionError(
                f"missing_runtime_artifact:{e.args[0]}",
                step_id=step.step_id,
                op=getattr(step, "op", None),
                artifact=getattr(step, "input_artifact", None),
            ) from e
        except Exception as e:
            raise ReducerExecutionError(
                str(e),
                step_id=step.step_id,
                op=getattr(step, "op", None),
                artifact=getattr(step, "input_artifact", None),
            ) from e

    final_artifact = artifacts[plan.final_artifact]
    return {
        "kind": final_artifact.kind,
        "rows": final_artifact.rows,
        "columns": final_artifact.columns,
        "artifacts": {
            name: {
                "kind": art.kind,
                "columns": art.columns,
                "row_count": len(art.rows),
            }
            for name, art in artifacts.items()
        },
    }
