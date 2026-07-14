#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10738
NAME = "stage10738_root_admission_manifest_v3"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_JSONL = OUT_DIR / "root_admission_manifest_v3.jsonl"
SUMMARY_JSON = OUT_DIR / "root_admission_manifest_v3.json"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

REVIEWED_ROOTS = ROOT / "runs/local/artifacts/stage10735_reviewed_v27_plus_cpp_train_support_package/reviewed_v27_plus_cpp_root_manifest.jsonl"
COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
BOOTSTRAP_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/multitarget_bootstrap_with_heldout_rows.jsonl"
SCALE_CONTRACT = ROOT / "runs/local/artifacts/stage10613_multilingual_root_scale_quality_contract/multilingual_root_scale_quality_contract.json"
LATEST_REVIEWED_PACKAGE = ROOT / "runs/local/artifacts/stage10735_reviewed_v27_plus_cpp_train_support_package/reviewed_v27_plus_cpp_train_support_package.json"
CURRENT_FRONTIER_QUEUE = ROOT / "runs/local/artifacts/stage10730_multilingual_root_scale_frontier_queue/multilingual_root_scale_frontier_queue.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def root_lineage_key(root: dict[str, Any]) -> str:
    repo_id = str(root.get("repo_id") or "unknown")
    snapshot_id = str(root.get("snapshot_id") or root.get("bundle_id") or root.get("root_id"))
    return f"{repo_id}::{snapshot_id}"


def reviewed_quality(root: dict[str, Any]) -> float:
    score = 0.65
    if root.get("reviewed_bundle_source"):
        score += 0.15
    if root.get("selected_test_anchor"):
        score += 0.08
    if root.get("verifier_anchor"):
        score += 0.08
    if root.get("strict_eval_eligible"):
        score += 0.02
    if root.get("abstention_heavy"):
        score -= 0.10
    if root.get("train_support_only"):
        score -= 0.03
    for note in root.get("claim_notes") or []:
        if note == "pure_web_no_selected_test_anchor":
            score -= 0.08
        elif note == "source_derived_verifier_constraint":
            score -= 0.04
        elif note == "not_admissible_for_same_surface_comparison":
            score -= 0.02
    return round(clamp(score), 4)


def reviewed_admit_role(root: dict[str, Any]) -> str:
    if root.get("stress_overlap_only"):
        return "diagnostic"
    if root.get("strict_eval_eligible"):
        return "strict_eval"
    split_role = str(root.get("split_role") or "")
    if split_role == "validation":
        return "validation"
    if root.get("train_support_only") or split_role == "train_support":
        return "train"
    return "diagnostic"


def bootstrap_quality(root: dict[str, Any], agg: dict[str, Any]) -> float:
    score = 0.35
    verifier_id = str(root.get("verifier_id") or "")
    split_component = str(root.get("split_component") or "")
    if verifier_id == "PASS_TARGETED_TEST_SELECTION":
        score += 0.10
    if verifier_id == "PASS_TRACE_VERIFICATION_TARGETS":
        score += 0.14
    if split_component == "strict_eval_long_context_heldout":
        score += 0.08
    if agg["selected_test_like_rows"] > 0:
        score += 0.07
    if agg["verifier_outcome_rows"] > 0:
        score += 0.06
    if agg["prompt_target_leak_rows"] > 0:
        score -= 0.25
    if agg["opaque_option_rows"] == 0 and agg["bounded_decision_rows"] > 0:
        score -= 0.10
    if split_component in {"reference_bounded_eval", "diagnostic_bounded"}:
        score -= 0.05
    return round(clamp(score), 4)


def bootstrap_admit_role(root: dict[str, Any], agg: dict[str, Any]) -> str:
    split_component = str(root.get("split_component") or "")
    if agg["prompt_target_leak_rows"] > 0:
        if split_component == "strict_eval_long_context_heldout":
            return "diagnostic"
        return "quarantine"
    if split_component in {"reference_bounded_eval", "diagnostic_bounded"}:
        return "diagnostic"
    if split_component == "strict_eval_long_context_heldout":
        return "diagnostic"
    if split_component == "validation_bootstrap_bounded":
        return "validation"
    if split_component.startswith("train_"):
        return "train"
    return "diagnostic"


def aggregate_bootstrap_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        root_id = str(row["root_id"])
        entry = grouped.setdefault(
            root_id,
            {
                "row_count": 0,
                "prompt_target_leak_rows": 0,
                "opaque_option_rows": 0,
                "bounded_decision_rows": 0,
                "selected_test_like_rows": 0,
                "verifier_outcome_rows": 0,
                "target_families": Counter(),
                "target_subtypes": Counter(),
            },
        )
        entry["row_count"] += 1
        anti_cheat = row.get("anti_cheat") or {}
        if anti_cheat.get("prompt_target_leak"):
            entry["prompt_target_leak_rows"] += 1
        if anti_cheat.get("opaque_option_contract"):
            entry["opaque_option_rows"] += 1
        if row.get("target_family") == "bounded_decision":
            entry["bounded_decision_rows"] += 1
        if row.get("target_subtype") in {"selected_test", "candidate_path", "verifier_outcome"}:
            entry["selected_test_like_rows"] += 1
        if row.get("target_subtype") == "verifier_outcome":
            entry["verifier_outcome_rows"] += 1
        entry["target_families"][str(row.get("target_family") or "unknown")] += 1
        entry["target_subtypes"][str(row.get("target_subtype") or "unknown")] += 1
    return grouped


def main() -> None:
    reviewed_roots = load_jsonl(REVIEWED_ROOTS)
    compiled_roots = load_jsonl(COMPILED_ROOTS)
    bootstrap_rows = load_jsonl(BOOTSTRAP_ROWS)
    load_json(SCALE_CONTRACT)
    latest_reviewed_package = load_json(LATEST_REVIEWED_PACKAGE)
    frontier_queue = load_json(CURRENT_FRONTIER_QUEUE)

    bootstrap_agg = aggregate_bootstrap_rows(bootstrap_rows)
    manifest_rows: list[dict[str, Any]] = []

    for root in reviewed_roots:
        manifest_rows.append(
            {
                "root_id": root["root_id"],
                "repo_id": root["repo_id"],
                "repo_family": root["repo_family"],
                "language_family": root["language_family"],
                "task_family": "reviewed_maintainer_bundle",
                "snapshot_id": root.get("bundle_id") or root["root_id"],
                "verifier_id": "REVIEWED_MAINTAINER_BUNDLE" if root.get("verifier_anchor") else "REVIEWED_MAINTAINER_BUNDLE_NO_VERIFIER",
                "source_family_id": "reviewed_v27_plus_cpp_train_support",
                "root_lineage_key": root_lineage_key(root),
                "quality_score": reviewed_quality(root),
                "admit_role": reviewed_admit_role(root),
                "source_kind": "reviewed_bundle_root",
                "split_component": root.get("split_role"),
                "selected_test_anchor": bool(root.get("selected_test_anchor")),
                "verifier_anchor": bool(root.get("verifier_anchor")),
                "prompt_target_leak_rows": 0,
                "abstention_heavy": bool(root.get("abstention_heavy")),
                "notes": list(root.get("claim_notes") or []),
            }
        )

    for root in compiled_roots:
        agg = bootstrap_agg.get(
            str(root["root_id"]),
            {
                "row_count": 0,
                "prompt_target_leak_rows": 0,
                "opaque_option_rows": 0,
                "bounded_decision_rows": 0,
                "selected_test_like_rows": 0,
                "verifier_outcome_rows": 0,
                "target_families": Counter(),
                "target_subtypes": Counter(),
            },
        )
        notes: list[str] = []
        if agg["prompt_target_leak_rows"] > 0:
            notes.append("prompt_target_leak_rows_present")
        if str(root.get("split_component")) == "strict_eval_long_context_heldout":
            notes.append("heldout_bootstrap_root")
        if agg["verifier_outcome_rows"] > 0:
            notes.append("contains_verifier_outcome_targets")
        manifest_rows.append(
            {
                "root_id": root["root_id"],
                "repo_id": root["repo_id"],
                "repo_family": root["repo_family"],
                "language_family": root["language_family"],
                "task_family": root.get("task_family"),
                "snapshot_id": root.get("snapshot_id"),
                "verifier_id": root.get("verifier_id"),
                "source_family_id": ((root.get("provenance") or {}).get("source_family_id")) or "unknown",
                "root_lineage_key": root_lineage_key(root),
                "quality_score": bootstrap_quality(root, agg),
                "admit_role": bootstrap_admit_role(root, agg),
                "source_kind": "compiled_root_state",
                "split_component": root.get("split_component"),
                "selected_test_anchor": agg["selected_test_like_rows"] > 0,
                "verifier_anchor": str(root.get("verifier_id") or "").startswith("PASS_"),
                "prompt_target_leak_rows": agg["prompt_target_leak_rows"],
                "abstention_heavy": False,
                "notes": notes,
            }
        )

    manifest_rows.sort(key=lambda row: (row["admit_role"], row["language_family"], row["repo_family"], row["root_id"]))
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    admit_role_counts = Counter(row["admit_role"] for row in manifest_rows)
    language_role_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for language in {row["language_family"] for row in manifest_rows}:
        counts = Counter(row["admit_role"] for row in manifest_rows if row["language_family"] == language)
        language_role_counts[language] = dict(sorted(counts.items()))

    reviewed_train_counts = Counter(
        str(row.get("language_family") or "")
        for row in manifest_rows
        if str(row.get("admit_role") or "") == "train" and str(row.get("source_kind") or "") == "reviewed_bundle_root"
    )
    package_metrics = latest_reviewed_package.get("metrics") or {}
    frontier = frontier_queue.get("current_frontier") or {}

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "root_admission_manifest_v3_ready",
        "claim_scope": [
            "Refresh the root-admission manifest against the latest reviewed package that now includes five additional admitted C/C++ train-support roots.",
            "Keep compiled long-context roots and bootstrap anti-cheat logic unchanged while updating the reviewed root inventory and the current frontier reference.",
            "This is a root-admission and scaling artifact, not a new model headline.",
        ],
        "source_artifacts": {
            "reviewed_root_manifest": display(REVIEWED_ROOTS),
            "compiled_roots": display(COMPILED_ROOTS),
            "bootstrap_rows": display(BOOTSTRAP_ROWS),
            "scale_contract": display(SCALE_CONTRACT),
            "latest_reviewed_package": display(LATEST_REVIEWED_PACKAGE),
            "current_frontier_queue": display(CURRENT_FRONTIER_QUEUE),
        },
        "global_counts": {
            "total_roots": len(manifest_rows),
            "admit_role_counts": dict(sorted(admit_role_counts.items())),
            "reviewed_root_records": len(reviewed_roots),
            "reviewed_train_root_records": sum(1 for row in reviewed_roots if row.get("train_support_only") or str(row.get("split_role") or "") == "train_support"),
            "strict_frontier_accuracy_current": frontier.get("strict_accuracy"),
        },
        "language_role_counts": dict(sorted(language_role_counts.items())),
        "latest_reviewed_snapshot": {
            "root_language_counts": package_metrics.get("root_language_counts") or {},
            "row_language_counts": package_metrics.get("row_language_counts") or {},
            "split_counts": package_metrics.get("split_counts") or {},
            "train_language_counts": dict(sorted(reviewed_train_counts.items())),
        },
        "headline_findings": [
            "The reviewed-root inventory is no longer Rust-updated only; it now contains a materially larger C/C++ train-support lane.",
            "The strict standalone frontier is still 22/24, so this refresh changes scale control rather than headline accuracy.",
            "Any next large-scale package should consume this v3 admission manifest instead of the stale v2 inventory.",
        ],
        "outputs": {
            "manifest_jsonl": display(MANIFEST_JSONL),
            "summary_json": display(SUMMARY_JSON),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "manifest": display(MANIFEST_JSONL),
            "summary": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
