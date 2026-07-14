#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11704_web_remaining_nonverifier_support_package"
OUT = ART / NAME
SUMMARY = OUT / "web_remaining_nonverifier_support_package.json"
TRAIN_ROWS = OUT / "web_remaining_nonverifier_support_rows.jsonl"
REJECTED_ROWS = OUT / "web_remaining_nonverifier_rejected_rows.jsonl"
WORKLIST = OUT / "web_remaining_nonverifier_worklist.jsonl"

MISSES = ART / "stage11703_web_transition_product_policy_integration_audit/web_transition_product_policy_remaining_misses.jsonl"
BRIDGED_ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"

SOURCES = {
    "canonical_train_support": ART / "stage11663_web_canonical_renderer_package/web_canonical_train_support.jsonl",
    "role_normalized_topup": ART / "stage11694_web_gap_role_normalized_topup_package/web_gap_role_normalized_topup_rows.jsonl",
    "identity_gap_topup_manifest": ART / "stage11695_web_identity_gap_topup_probe_request/web_identity_gap_topup_train_manifest.jsonl",
    "same_role_counterfactual": ART / "stage11678_web_remaining_miss_counterfactual_builder/web_same_role_identity_counterfactual_train.jsonl",
    "grouped_verified_materialization": ART / "stage11650_web_gap_grouped_verified_materialization/web_gap_grouped_verified_rows.jsonl",
}

TARGET_TASKS = {"symptom_localization", "minimal_fix_selection"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or "")


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [opt for opt in (row.get("opaque_options") or ((row.get("standalone_projection_source") or {}).get("opaque_options") or [])) if isinstance(opt, dict)]


def option_label(opt: dict[str, Any]) -> str:
    return str(opt.get("label") or "").strip()


def option_role(opt: dict[str, Any]) -> str:
    obj = opt.get("canonical_candidate_object") if isinstance(opt.get("canonical_candidate_object"), dict) else {}
    sem = opt.get("semantic_candidate") if isinstance(opt.get("semantic_candidate"), dict) else {}
    return str(opt.get("role") or obj.get("role") or sem.get("role") or opt.get("semantic_role") or "").strip()


def target_option(row: dict[str, Any]) -> dict[str, Any]:
    target = target_label(row)
    for opt in options(row):
        if option_label(opt) == target:
            return opt
    return {}


def target_role(row: dict[str, Any]) -> str:
    return option_role(target_option(row))


def role_counts(row: dict[str, Any]) -> Counter[str]:
    return Counter(option_role(opt) for opt in options(row) if option_role(opt))


def pre_candidate_text(row: dict[str, Any]) -> str:
    text = str(row.get("prompt") or row.get("input_text") or row.get("encoder_text") or row.get("text") or "").lower()
    return text.split("candidates", 1)[0]


def option_value(opt: dict[str, Any]) -> str:
    obj = opt.get("canonical_candidate_object") if isinstance(opt.get("canonical_candidate_object"), dict) else {}
    sem = opt.get("semantic_candidate") if isinstance(opt.get("semantic_candidate"), dict) else {}
    return str(obj.get("value") or sem.get("canonical_value") or sem.get("option_value") or opt.get("value") or opt.get("text") or "").strip()


def leak_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    opts = options(row)
    if len(opts) <= 1:
        reasons.append("singleton_or_missing_options")
    target = target_label(row)
    before = pre_candidate_text(row)
    if target and re.search(rf"(?:option|candidate|answer|label)\s+{re.escape(target.lower())}\b|\b{re.escape(target.lower())}\s*:", before):
        reasons.append("prompt_label_leak_before_options")
    value = option_value(target_option(row)).lower()
    if value and value in before:
        reasons.append("prompt_target_value_leak_before_options")
    return reasons


def lane_for(row: dict[str, Any]) -> str:
    task = str(row.get("task_type") or "")
    t_role = target_role(row)
    counts = role_counts(row)
    repo = str(row.get("repo_id") or row.get("repo_family") or "")
    if task not in TARGET_TASKS:
        return ""
    if task == "symptom_localization" and t_role == "verifier_and_test_constraint" and counts.get("candidate_change_surface", 0) >= 1:
        return "symptom_verifier_linked_vs_candidate_surface"
    if task == "symptom_localization" and t_role == "candidate_change_surface" and counts.get("candidate_change_surface", 0) >= 2:
        return "symptom_same_role_candidate_change_surface"
    if task == "minimal_fix_selection" and t_role == "candidate_change_surface" and counts.get("candidate_change_surface", 0) >= 2:
        return "minimal_fix_same_role_candidate_change_surface"
    if task == "minimal_fix_selection" and t_role == "candidate_change_surface" and "openhands" in repo and counts.get("candidate_change_surface", 0) >= 1:
        return "minimal_fix_openhands_candidate_surface"
    return ""


def source_rows() -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for source_name, path in SOURCES.items():
        for row in load_jsonl(path):
            rid = row_id(row)
            if not rid or rid in seen:
                continue
            seen.add(rid)
            clone = dict(row)
            clone["stage11704_source"] = source_name
            out.append(clone)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    misses = load_jsonl(MISSES)
    heldout_roots = {root_id(row) for row in load_jsonl(BRIDGED_ROWS)}
    miss_lanes = []
    for row in misses:
        miss_lanes.append(
            {
                "row_id": row.get("row_id"),
                "root_id": row.get("root_id"),
                "repo_id": row.get("repo_id"),
                "task_type": row.get("task_type"),
                "target_role": row.get("target_role"),
                "predicted_role": row.get("product_predicted_role"),
                "needed_lane": (
                    "symptom_verifier_linked_vs_candidate_surface"
                    if row.get("task_type") == "symptom_localization" and row.get("target_role") == "verifier_and_test_constraint"
                    else "minimal_fix_same_role_candidate_change_surface"
                    if row.get("task_type") == "minimal_fix_selection"
                    else "symptom_same_role_candidate_change_surface"
                ),
            }
        )

    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in source_rows():
        reasons = []
        if root_id(row) in heldout_roots:
            reasons.append("heldout_root_overlap")
        if str(row.get("task_type") or "") not in TARGET_TASKS:
            reasons.append("non_target_task")
        lane = lane_for(row)
        if not lane:
            reasons.append("does_not_match_remaining_miss_geometry")
        reasons.extend(leak_reasons(row))
        if reasons:
            rejected.append({"row_id": row_id(row), "root_id": root_id(row), "task_type": row.get("task_type"), "source": row.get("stage11704_source"), "reasons": reasons})
            continue
        clone = dict(row)
        clone["stage11704_lane"] = lane
        clone["train_support_only"] = True
        clone["strict_eval_eligible_now"] = False
        clone["stage11704_remaining_nonverifier_support"] = True
        admitted.append(clone)

    write_jsonl(TRAIN_ROWS, admitted)
    write_jsonl(REJECTED_ROWS, rejected)
    write_jsonl(WORKLIST, miss_lanes)

    lane_counts = Counter(row.get("stage11704_lane") for row in admitted)
    root_counts = Counter(root_id(row) for row in admitted)
    source_counts = Counter(row.get("stage11704_source") for row in admitted)
    repo_counts = Counter(str(row.get("repo_id") or row.get("repo_family") or "") for row in admitted)
    gates = {
        "has_support_rows": len(admitted) > 0,
        "no_heldout_root_overlap": not ({root_id(row) for row in admitted} & heldout_roots),
        "has_symptom_verifier_linked_support": lane_counts.get("symptom_verifier_linked_vs_candidate_surface", 0) >= 10,
        "has_same_role_candidate_change_support": (
            lane_counts.get("symptom_same_role_candidate_change_surface", 0)
            + lane_counts.get("minimal_fix_same_role_candidate_change_surface", 0)
            + lane_counts.get("minimal_fix_openhands_candidate_surface", 0)
        ) >= 10,
        "unique_roots_at_least_20": len(root_counts) >= 20,
        "all_rows_train_support_only": all(row.get("train_support_only") is True and row.get("strict_eval_eligible_now") is False for row in admitted),
    }
    decision = "remaining_nonverifier_support_ready_for_guarded_probe" if all(gates.values()) else "remaining_nonverifier_support_needs_more_supply"
    summary = {
        "stage": 11704,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "counts": {
            "remaining_misses": len(misses),
            "admitted_rows": len(admitted),
            "admitted_unique_roots": len(root_counts),
            "rejected_rows": len(rejected),
            "lanes": dict(lane_counts.most_common()),
            "sources": dict(source_counts.most_common()),
            "repos": dict(repo_counts.most_common()),
            "top_roots": root_counts.most_common(15),
            "reject_reasons": dict(Counter(reason for row in rejected for reason in row["reasons"]).most_common()),
        },
        "worklist": {
            "rows": len(miss_lanes),
            "needed_lanes": dict(Counter(row["needed_lane"] for row in miss_lanes).most_common()),
            "misses": miss_lanes,
        },
        "gates": gates,
        "recommended_next": (
            [
                "Run one guarded head-only probe from this package plus protected replay.",
                "Promotion requires Stage11703 Web >=60/66, protected gates preserved, and remaining misses fewer than 6.",
            ]
            if all(gates.values())
            else [
                "Do not run a training probe yet.",
                "Materialize more disjoint symptom/localization and minimal-fix same-role candidate rows, especially Llama/OpenHands analogues.",
            ]
        ),
        "source_artifacts": {
            "misses": rel(MISSES),
            "bridged_rows": rel(BRIDGED_ROWS),
            "sources": {name: rel(path) for name, path in SOURCES.items()},
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "train_rows": rel(TRAIN_ROWS),
            "rejected_rows": rel(REJECTED_ROWS),
            "worklist": rel(WORKLIST),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "counts": summary["counts"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
