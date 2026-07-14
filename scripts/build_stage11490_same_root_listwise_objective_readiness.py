#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11490
NAME = "stage11490_same_root_listwise_objective_readiness"
OUT = ART / NAME
SUMMARY = OUT / "same_root_listwise_objective_readiness.json"
ROW_AUDIT = OUT / "same_root_listwise_group_audit.jsonl"

RESIDUAL50 = ART / "stage11481_residual50_ready_package_with_rust_counters/residual50_ready_rows.jsonl"
MANIFEST = ART / "stage11486_residual50_sampler_ablation_probe_request/residual50_sampler_ablation_probe_manifest.jsonl"
STAGE11489 = ART / "stage11489_residual50_sampler_ablation_decision/residual50_sampler_ablation_decision.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def group_key(row: dict[str, Any]) -> str:
    for key in ("candidate_set_id", "state_id", "same_root_candidate_group_id", "listwise_group_id"):
        value = row.get(key)
        if value:
            return str(value)
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    for key in ("candidate_set_id", "state_id", "same_root_candidate_group_id", "listwise_group_id"):
        value = source.get(key)
        if value:
            return str(value)
    return ""


def option_value_for_target(row: dict[str, Any]) -> str:
    target = str(row.get("bounded_choice_target_label") or "").strip()
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    options = source.get("opaque_options") or row.get("opaque_options") or []
    for option in options:
        if isinstance(option, dict) and str(option.get("label") or "").strip() == target:
            return str(option.get("value") or "").strip()
    return ""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    residual50 = read_jsonl(RESIDUAL50)
    manifest_rows = read_jsonl(MANIFEST)
    train_rows = [row for row in manifest_rows if row.get("split") == "train"]
    stage11489 = read_json(STAGE11489)

    root_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_candidate_group_id = 0
    rows_with_options = 0
    for row in residual50:
        root_groups[root_key(row)].append(row)
        if not group_key(row):
            missing_candidate_group_id += 1
        source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
        if source.get("opaque_options") or row.get("opaque_options"):
            rows_with_options += 1

    group_rows: list[dict[str, Any]] = []
    duplicate_root_groups = 0
    duplicate_roots_with_target_role_conflict = 0
    roots_with_candidate_and_verifier_targets = 0
    for root, rows in sorted(root_groups.items()):
        target_values = [option_value_for_target(row) for row in rows]
        target_counter = Counter(value for value in target_values if value)
        has_conflict = len(target_counter) > 1
        if len(rows) > 1:
            duplicate_root_groups += 1
        if len(rows) > 1 and has_conflict:
            duplicate_roots_with_target_role_conflict += 1
        if "candidate_change_surface" in target_counter and "verifier_and_test_constraint" in target_counter:
            roots_with_candidate_and_verifier_targets += 1
        group_rows.append(
            {
                "root_id": root,
                "rows": len(rows),
                "explicit_group_ids": sorted({group_key(row) for row in rows if group_key(row)}),
                "target_values": dict(sorted(target_counter.items())),
                "conflicting_target_values_under_same_root": has_conflict,
                "row_ids": [str(row.get("row_id") or "") for row in rows],
            }
        )
    write_jsonl(ROW_AUDIT, group_rows)

    train_task_counts = Counter(str(row.get("task_type") or "unknown") for row in train_rows)
    train_target_values = Counter(option_value_for_target(row) for row in train_rows if option_value_for_target(row))
    readiness_passed = (
        rows_with_options == len(residual50)
        and missing_candidate_group_id == 0
        and duplicate_roots_with_target_role_conflict == 0
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "same_root_listwise_objective_not_ready" if not readiness_passed else "same_root_listwise_objective_ready",
        "readiness_passed": readiness_passed,
        "findings": {
            "residual50_rows": len(residual50),
            "residual50_unique_roots": len(root_groups),
            "rows_with_opaque_options": rows_with_options,
            "rows_missing_explicit_candidate_group_id": missing_candidate_group_id,
            "duplicate_root_groups": duplicate_root_groups,
            "duplicate_roots_with_target_role_conflict": duplicate_roots_with_target_role_conflict,
            "roots_with_candidate_and_verifier_targets": roots_with_candidate_and_verifier_targets,
            "train_rows": len(train_rows),
            "train_task_counts": dict(sorted(train_task_counts.items())),
            "train_target_value_counts": dict(sorted(train_target_values.items())),
        },
        "interpretation": [
            "The existing trainer already applies per-row option-softmax CE through bounded_choice_aux_loss.",
            "A new same-root listwise objective must not group only by root_id because Residual-50 contains counterfactual/projected rows from the same root with different target roles.",
            "The missing schema field is an explicit candidate_set_id/state_id/listwise_group_id that identifies rows sharing the same visible state and mutually exclusive candidate set.",
        ],
        "blocked_next_training": {
            "reason": "Naive root_id grouping would train contradictory targets together.",
            "required_before_training": [
                "add explicit listwise_group_id or candidate_set_id to Residual-50 rows",
                "ensure each group has exactly one gold candidate role or an explicit multi-gold/set-valued target",
                "include at least one hard negative from candidate_change_surface/verifier_and_test_constraint/symptom_or_call_path_analogue per group",
                "keep protected validation/strict/residual rows outside train groups",
            ],
        },
        "next_stage_contract": {
            "recommended_stage": "stage11491_residual50_listwise_group_compiler",
            "goal": "compile safe candidate-set groups from Stage11481 without changing training data membership",
            "success_criteria": [
                "all emitted groups have explicit listwise_group_id",
                "no group has contradictory singleton targets",
                "no protected row/root overlap",
                "group audit exposes role margins required for later product scorer comparison",
            ],
        },
        "stage11489_reference": {
            "decision": stage11489.get("decision"),
            "next_hypothesis": ((stage11489.get("next_experiment_contract") or {}).get("hypothesis_id")),
        },
        "source_artifacts": {
            "residual50_rows": rel(RESIDUAL50),
            "stage11486_manifest": rel(MANIFEST),
            "stage11489_decision": rel(STAGE11489),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "row_audit": rel(ROW_AUDIT),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "readiness_passed": readiness_passed, "findings": summary["findings"], "next_stage_contract": summary["next_stage_contract"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
