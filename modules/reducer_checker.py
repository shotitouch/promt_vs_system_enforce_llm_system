from __future__ import annotations

from typing import Any, Dict, List, Optional

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

ArtifactState = Dict[str, Any]


def _artifact_state(
    kind: str, columns: List[str], group_keys: Optional[List[str]] = None
) -> ArtifactState:
    return {
        "kind": kind,
        "columns": list(columns),
        "group_keys": list(group_keys or []),
    }


def _require_columns(
    artifact_name: str,
    artifact: ArtifactState,
    required: List[str],
    errors: List[str],
) -> None:
    cols = set(artifact["columns"])
    missing = [c for c in required if c not in cols]
    if missing:
        errors.append(
            f"artifact '{artifact_name}' is missing required columns: {missing}"
        )


def check_reduction_plan(plan: ReductionPlan, reducer_input: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    input_artifact_name = reducer_input["input_artifact"]
    input_kind = reducer_input["kind"]
    input_columns = reducer_input["columns"]

    if plan.status == "unsupported":
        if plan.steps:
            errors.append("unsupported plan must not contain steps")
        if plan.final_artifact is not None:
            errors.append("unsupported plan must omit final_artifact")
        if plan.final_kind is not None:
            errors.append("unsupported plan must omit final_kind")
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "artifacts": {},
        }

    if plan.status == "no_reduction_needed":
        if plan.steps:
            errors.append("no_reduction_needed plan must not contain steps")
        if plan.final_artifact != input_artifact_name:
            errors.append(
                f"no_reduction_needed final_artifact must be '{input_artifact_name}'"
            )
        if plan.final_kind != input_kind:
            errors.append(
                f"no_reduction_needed final_kind must match input kind '{input_kind}'"
            )
        artifacts = {
            input_artifact_name: _artifact_state(
                kind=input_kind,
                columns=input_columns,
            )
        }
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "artifacts": artifacts,
        }

    if not plan.steps:
        errors.append("supported plan must contain steps")
        return {
            "passed": False,
            "errors": errors,
            "warnings": warnings,
            "artifacts": {},
        }

    artifacts: Dict[str, ArtifactState] = {
        input_artifact_name: _artifact_state(
            kind=input_kind,
            columns=input_columns,
        )
    }

    seen_step_ids = set()

    for step in plan.steps:
        if step.step_id in seen_step_ids:
            errors.append(f"duplicate step_id: {step.step_id}")
        seen_step_ids.add(step.step_id)

        if isinstance(step, MergeOnKeysStep):
            if step.left_artifact not in artifacts:
                errors.append(
                    f"step '{step.step_id}' references unknown left_artifact '{step.left_artifact}'"
                )
                continue
            if step.right_artifact not in artifacts:
                errors.append(
                    f"step '{step.step_id}' references unknown right_artifact '{step.right_artifact}'"
                )
                continue
            if step.output_artifact in artifacts:
                errors.append(
                    f"step '{step.step_id}' reuses existing output_artifact '{step.output_artifact}'"
                )
                continue

            left = artifacts[step.left_artifact]
            right = artifacts[step.right_artifact]

            if left["kind"] != "table" or right["kind"] != "table":
                errors.append(
                    f"step '{step.step_id}' merge_on_keys requires table + table inputs"
                )
                continue

            _require_columns(step.left_artifact, left, step.keys, errors)
            _require_columns(step.right_artifact, right, step.keys, errors)

            merged_cols = list(left["columns"])
            for col in right["columns"]:
                if col not in merged_cols:
                    merged_cols.append(col)

            artifacts[step.output_artifact] = _artifact_state("table", merged_cols)
            continue

        if step.input_artifact not in artifacts:
            errors.append(
                f"step '{step.step_id}' references unknown input_artifact '{step.input_artifact}'"
            )
            continue

        if step.output_artifact in artifacts:
            errors.append(
                f"step '{step.step_id}' reuses existing output_artifact '{step.output_artifact}'"
            )
            continue

        src = artifacts[step.input_artifact]
        src_kind = src["kind"]
        src_cols = list(src["columns"])
        group_keys = list(src.get("group_keys", []))

        if isinstance(step, GroupByStep):
            if src_kind != "table":
                errors.append(f"step '{step.step_id}' group_by requires table input")
                continue
            _require_columns(step.input_artifact, src, step.keys, errors)
            artifacts[step.output_artifact] = _artifact_state(
                "grouped_table",
                src_cols,
                group_keys=step.keys,
            )

        elif isinstance(step, SortByStep):
            if src_kind not in {"table", "grouped_table"}:
                errors.append(
                    f"step '{step.step_id}' sort_by requires table or grouped_table input"
                )
                continue
            _require_columns(step.input_artifact, src, step.by, errors)
            artifacts[step.output_artifact] = _artifact_state(
                src_kind,
                src_cols,
                group_keys=group_keys,
            )

        elif isinstance(step, (TakeFirstStep, TakeLastStep, TakeMinStep, TakeMaxStep)):
            if src_kind not in {"table", "grouped_table"}:
                errors.append(
                    f"step '{step.step_id}' row-selection op requires table or grouped_table input"
                )
                continue
            if isinstance(step, (TakeMinStep, TakeMaxStep)):
                _require_columns(step.input_artifact, src, [step.by_column], errors)
            artifacts[step.output_artifact] = _artifact_state("table", src_cols)

        elif isinstance(step, SelectColumnsStep):
            if src_kind != "table":
                errors.append(
                    f"step '{step.step_id}' select_columns requires table input"
                )
                continue
            _require_columns(step.input_artifact, src, step.columns, errors)
            artifacts[step.output_artifact] = _artifact_state("table", step.columns)

        elif isinstance(step, RenameColumnsStep):
            if src_kind != "table":
                errors.append(
                    f"step '{step.step_id}' rename_columns requires table input"
                )
                continue
            _require_columns(
                step.input_artifact, src, list(step.rename_map.keys()), errors
            )
            new_cols = [step.rename_map.get(c, c) for c in src_cols]
            artifacts[step.output_artifact] = _artifact_state("table", new_cols)

        elif isinstance(step, (SubtractStep, AddStep, MultiplyStep)):
            if src_kind != "table":
                errors.append(
                    f"step '{step.step_id}' arithmetic op requires table input"
                )
                continue
            _require_columns(
                step.input_artifact, src, [step.left_column, step.right_column], errors
            )
            new_cols = list(src_cols)
            if step.output_column not in new_cols:
                new_cols.append(step.output_column)
            artifacts[step.output_artifact] = _artifact_state("table", new_cols)

        elif isinstance(step, DivideStep):
            if src_kind != "table":
                errors.append(f"step '{step.step_id}' divide requires table input")
                continue
            _require_columns(
                step.input_artifact,
                src,
                [step.numerator_column, step.denominator_column],
                errors,
            )
            new_cols = list(src_cols)
            if step.output_column not in new_cols:
                new_cols.append(step.output_column)
            artifacts[step.output_artifact] = _artifact_state("table", new_cols)

        elif isinstance(step, AbsStep):
            if src_kind != "table":
                errors.append(f"step '{step.step_id}' abs requires table input")
                continue
            _require_columns(step.input_artifact, src, [step.source_column], errors)
            new_cols = list(src_cols)
            if step.output_column not in new_cols:
                new_cols.append(step.output_column)
            artifacts[step.output_artifact] = _artifact_state("table", new_cols)

        elif isinstance(step, CompareStep):
            if src_kind != "table":
                errors.append(f"step '{step.step_id}' compare requires table input")
                continue
            _require_columns(
                step.input_artifact, src, [step.left_column, step.right_column], errors
            )
            new_cols = list(src_cols)
            if step.output_column not in new_cols:
                new_cols.append(step.output_column)
            artifacts[step.output_artifact] = _artifact_state("table", new_cols)

        elif isinstance(step, AggregateStatStep):
            if src_kind == "table":
                if step.statistic != "count" and step.source_column is None:
                    errors.append(
                        f"step '{step.step_id}' aggregate_stat requires source_column for statistic '{step.statistic}'"
                    )
                    continue
                if step.source_column is not None:
                    _require_columns(
                        step.input_artifact, src, [step.source_column], errors
                    )
                artifacts[step.output_artifact] = _artifact_state(
                    "scalar", [step.output_column]
                )

            elif src_kind == "grouped_table":
                if step.statistic != "count" and step.source_column is None:
                    errors.append(
                        f"step '{step.step_id}' aggregate_stat requires source_column for grouped statistic '{step.statistic}'"
                    )
                    continue
                if step.source_column is not None:
                    _require_columns(
                        step.input_artifact, src, [step.source_column], errors
                    )
                out_cols = list(group_keys)
                if step.output_column not in out_cols:
                    out_cols.append(step.output_column)
                artifacts[step.output_artifact] = _artifact_state("table", out_cols)

            else:
                errors.append(
                    f"step '{step.step_id}' aggregate_stat requires table or grouped_table input"
                )

        elif isinstance(step, ProportionTrueStep):
            if src_kind != "table":
                errors.append(
                    f"step '{step.step_id}' proportion_true requires table input"
                )
                continue
            _require_columns(step.input_artifact, src, [step.source_column], errors)
            artifacts[step.output_artifact] = _artifact_state(
                "scalar", [step.output_column]
            )

        else:
            errors.append(
                f"step '{step.step_id}' has unsupported runtime type '{type(step).__name__}'"
            )

    if plan.final_artifact not in artifacts:
        errors.append(f"final_artifact '{plan.final_artifact}' was never produced")
    else:
        inferred_kind = artifacts[plan.final_artifact]["kind"]
        if inferred_kind != plan.final_kind:
            errors.append(
                f"final_kind mismatch for '{plan.final_artifact}': "
                f"declared='{plan.final_kind}', inferred='{inferred_kind}'"
            )

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "artifacts": artifacts,
    }
