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
NAME = "stage11693_web_gap_targeted_support_inventory"
OUT = ART / NAME
SUMMARY = OUT / "web_gap_targeted_support_inventory.json"
SUPPORT_ROWS = OUT / "web_gap_targeted_support_rows.jsonl"
BLOCKED_ROWS = OUT / "web_gap_targeted_blocked_rows.jsonl"

TRAIN = ART / "stage11663_web_canonical_renderer_package/web_canonical_train_support.jsonl"
GAP = ART / "stage11692_web_bridged_miss_family_audit/web_bridged_gemma_margin_rows.jsonl"
HELDOUT = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"

TARGET_TASKS = {"verifier_outcome", "symptom_localization", "minimal_fix_selection"}


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


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id"))


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def option_role(option: dict[str, Any]) -> str:
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    semantic = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    return str(option.get("role") or obj.get("role") or semantic.get("role") or "unknown")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    opts = source.get("opaque_options") if isinstance(source.get("opaque_options"), list) else row.get("opaque_options")
    return [opt for opt in opts or [] if isinstance(opt, dict)]


def target_role(row: dict[str, Any]) -> str:
    label = target_label(row)
    for option in options(row):
        if str(option.get("label")) == label:
            return option_role(option)
    return "unknown"


def role_counts(row: dict[str, Any]) -> Counter[str]:
    return Counter(option_role(option) for option in options(row))


def no_leak(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    return (
        anti.get("gold_label_visible_before_options") is not True
        and anti.get("no_gold_label_in_prompt_before_options") is not False
        and len(options(row)) > 1
    )


def classify_need(row: dict[str, Any]) -> str:
    task = str(row.get("task_type") or "")
    role = target_role(row)
    counts = role_counts(row)
    if task == "verifier_outcome":
        return "verifier_transition_same_role"
    if task == "symptom_localization" and role == "verifier_and_test_constraint":
        return "symptom_verifier_vs_candidate_surface"
    if task in {"symptom_localization", "minimal_fix_selection"} and role == "candidate_change_surface" and counts.get(role, 0) >= 2:
        return "same_role_source_or_fix_discrimination"
    return "adjacent_support"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train_rows = load_jsonl(TRAIN)
    gap_rows = load_jsonl(GAP)
    heldout_rows = load_jsonl(HELDOUT)
    heldout_roots = {root_key(row) for row in heldout_rows}
    gap_roots = {root_key(row) for row in gap_rows}
    needs = Counter(classify_need(row) for row in gap_rows)
    gap_tasks = Counter(str(row.get("task_type") or "unknown") for row in gap_rows)
    gap_roles = Counter(str(row.get("target_role") or "unknown") for row in gap_rows)
    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in train_rows:
        task = str(row.get("task_type") or "")
        if task not in TARGET_TASKS:
            continue
        reason = None
        if root_key(row) in heldout_roots or root_key(row) in gap_roots:
            reason = "heldout_or_gap_root_overlap"
        elif not no_leak(row):
            reason = "leak_or_singleton_risk"
        need = classify_need(row)
        out = dict(row)
        out["stage11693_gap_need_family"] = need
        out["stage11693_target_role"] = target_role(row)
        out["stage11693_role_counts"] = dict(role_counts(row))
        if reason is None:
            admitted.append(out)
        else:
            out["stage11693_block_reason"] = reason
            blocked.append(out)
    write_jsonl(SUPPORT_ROWS, admitted)
    write_jsonl(BLOCKED_ROWS, blocked)
    by_need: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in admitted:
        by_need[str(row["stage11693_gap_need_family"])].append(row)
    gates = {
        "has_verifier_transition_support": len(by_need.get("verifier_transition_same_role", [])) >= 20,
        "has_symptom_verifier_surface_support": len(by_need.get("symptom_verifier_vs_candidate_surface", [])) >= 10,
        "has_same_role_source_fix_support": len(by_need.get("same_role_source_or_fix_discrimination", [])) >= 10,
        "no_heldout_root_overlap": not ({root_key(row) for row in admitted} & heldout_roots),
        "support_rows_at_least_40": len(admitted) >= 40,
        "support_roots_at_least_10": len({root_key(row) for row in admitted}) >= 10,
    }
    if all(gates.values()):
        decision = "targeted_web_gap_support_inventory_ready_for_guarded_probe"
    else:
        decision = "targeted_web_gap_support_inventory_insufficient"
    summary = {
        "stage": 11693,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "gap_characterization": {
            "gap_rows": len(gap_rows),
            "gap_roots": len(gap_roots),
            "gap_task_counts": dict(gap_tasks.most_common()),
            "gap_target_role_counts": dict(gap_roles.most_common()),
            "gap_need_counts": dict(needs.most_common()),
        },
        "support_inventory": {
            "candidate_train_rows_scanned": len(train_rows),
            "admitted_rows": len(admitted),
            "admitted_roots": len({root_key(row) for row in admitted}),
            "blocked_rows": len(blocked),
            "admitted_by_need": dict(Counter(str(row["stage11693_gap_need_family"]) for row in admitted).most_common()),
            "admitted_by_task": dict(Counter(str(row.get("task_type") or "unknown") for row in admitted).most_common()),
            "admitted_by_target_role": dict(Counter(str(row["stage11693_target_role"]) for row in admitted).most_common()),
            "admitted_by_repo": dict(Counter(str(row.get("repo_id") or row.get("repo_family") or "unknown") for row in admitted).most_common()),
            "blocked_reasons": dict(Counter(str(row.get("stage11693_block_reason")) for row in blocked).most_common()),
        },
        "gates": gates,
        "recommended_next": [
            "If ready, run a guarded head-only probe using these support rows plus protected replay; promotion requires Web bridged >56/66 and protected gates preserved.",
            "If insufficient, materialize fresh disjoint Web roots specifically for verifier_transition_same_role and same_role_source_or_fix_discrimination.",
            "Do not train on the 66 bridged heldout rows or the 13 Gemma-margin rows.",
        ],
        "claim_boundary": [
            "This is support inventory only. It does not train or improve the model by itself.",
            "Rows are selected from existing canonical train-support roots and exclude bridged heldout roots.",
        ],
        "source_artifacts": {"train": rel(TRAIN), "gap": rel(GAP), "heldout": rel(HELDOUT)},
        "outputs": {"summary": rel(SUMMARY), "support_rows": rel(SUPPORT_ROWS), "blocked_rows": rel(BLOCKED_ROWS)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "gap": summary["gap_characterization"], "support": summary["support_inventory"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
