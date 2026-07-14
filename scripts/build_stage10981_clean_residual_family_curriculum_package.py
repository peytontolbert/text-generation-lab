#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10981
NAME = "stage10981_clean_residual_family_curriculum_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "clean_residual_family_curriculum_package.json"
ROWS_JSONL = OUT_DIR / "train_support_rows.jsonl"
INVENTORY_JSONL = OUT_DIR / "curriculum_inventory.jsonl"

ROOT_SPLIT_TRAIN = ARTIFACTS / "stage10786_larger_root_split_multilingual_training_package" / "agentkernel_lite_encdec_train.jsonl"
ROOT_SPLIT_SUMMARY = ARTIFACTS / "stage10786_larger_root_split_multilingual_training_package" / "larger_root_split_multilingual_training_package.json"
PYTHON_SUPPORT_TRAIN = ARTIFACTS / "stage10904_python_verifier_transition_support_package" / "agentkernel_lite_encdec_train.jsonl"
PYTHON_SUPPORT_SUMMARY = ARTIFACTS / "stage10904_python_verifier_transition_support_package" / "python_verifier_transition_support_package.json"
RUST_CLEAN_ROWS = ARTIFACTS / "stage10979_reviewed_evidence_role_curriculum_package" / "support_rows_clean.jsonl"
RUST_CLEAN_SUMMARY = ARTIFACTS / "stage10979_reviewed_evidence_role_curriculum_package" / "reviewed_evidence_role_curriculum_package.json"
BASE_VALIDATION = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package" / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package" / "agentkernel_lite_encdec_strict_eval.jsonl"

KEEP_ROOT_SPLIT_TASKS = {"evidence_citation", "verifier_outcome", "symptom_localization", "patch_impact", "abstention_insufficient_evidence"}
KEEP_PYTHON_SUPPORT_TASKS = {"evidence_role_classification", "verifier_candidate_role_classification", "verifier_outcome", "evidence_citation"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def overlay_roots() -> set[str]:
    roots: set[str] = set()
    for row in load_jsonl(BASE_VALIDATION) + load_jsonl(BASE_STRICT):
        source_root = str(row.get("source_root_id") or row.get("source_bundle_id") or "")
        if source_root:
            roots.add(source_root)
    return roots


def sanitize_train_row(row: dict[str, Any], *, source_stage: str) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    updated["curriculum_source_stage"] = source_stage
    return updated


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("row_id") or ""),
            str(row.get("task_type") or ""),
            str(row.get("target_text") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def classify_clean(rows: list[dict[str, Any]], heldout_roots: set[str]) -> list[dict[str, Any]]:
    clean_rows: list[dict[str, Any]] = []
    for row in rows:
        source_root = str(row.get("source_root_id") or row.get("source_bundle_id") or "")
        if source_root and source_root in heldout_roots:
            continue
        clean_rows.append(row)
    return clean_rows


def inventory(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "row_id": row.get("row_id"),
                "language_family": row.get("language_family"),
                "repo_family": row.get("repo_family"),
                "source_root_id": row.get("source_root_id"),
                "source_bundle_id": row.get("source_bundle_id"),
                "task_type": row.get("task_type"),
                "objective_family": row.get("objective_family"),
                "target_text": row.get("target_text"),
                "target_value": (row.get("standalone_projection_source") or {}).get("gold_value", row.get("target_text")),
                "selected_test_anchor": bool(row.get("selected_test_anchor")),
                "verifier_anchor": bool(row.get("verifier_anchor")),
                "curriculum_source_stage": row.get("curriculum_source_stage"),
            }
        )
    items.sort(key=lambda item: (str(item.get("language_family") or ""), str(item.get("task_type") or ""), str(item.get("row_id") or "")))
    return items


def counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    heldout_roots = overlay_roots()
    root_split_rows = [
        sanitize_train_row(row, source_stage="stage10786_root_split")
        for row in load_jsonl(ROOT_SPLIT_TRAIN)
        if str(row.get("task_type") or "") in KEEP_ROOT_SPLIT_TASKS
    ]
    python_rows = [
        sanitize_train_row(row, source_stage="stage10904_python_support")
        for row in load_jsonl(PYTHON_SUPPORT_TRAIN)
        if str(row.get("task_type") or "") in KEEP_PYTHON_SUPPORT_TASKS
    ]
    rust_rows = [
        sanitize_train_row(row, source_stage="stage10979_clean_reviewed")
        for row in load_jsonl(RUST_CLEAN_ROWS)
    ]

    rows = dedupe_rows(root_split_rows + python_rows + rust_rows)
    clean_rows = classify_clean(rows, heldout_roots)

    root_split_summary = load_json(ROOT_SPLIT_SUMMARY)
    python_summary = load_json(PYTHON_SUPPORT_SUMMARY)
    rust_summary = load_json(RUST_CLEAN_SUMMARY)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(clean_rows),
        "decision": "clean_residual_family_curriculum_packaged_from_root_split_and_support_only_sources",
        "claim_scope": [
            "Build a genuinely usable clean train-support curriculum for the remaining evidence and verifier boundaries from root-split or support-only sources.",
            "Avoid the reviewed-bundle overlap trap by excluding any source roots that belong to the current overlay validation or strict families.",
        ],
        "source_artifacts": {
            "root_split_summary": rel(ROOT_SPLIT_SUMMARY),
            "root_split_train_rows": rel(ROOT_SPLIT_TRAIN),
            "python_support_summary": rel(PYTHON_SUPPORT_SUMMARY),
            "python_support_train_rows": rel(PYTHON_SUPPORT_TRAIN),
            "rust_clean_summary": rel(RUST_CLEAN_SUMMARY),
            "rust_clean_rows": rel(RUST_CLEAN_ROWS),
            "overlay_validation_rows": rel(BASE_VALIDATION),
            "overlay_strict_rows": rel(BASE_STRICT),
        },
        "headline_findings": [
            "The usable clean curriculum is much larger when it is built from the older root-split train base plus support-only Python semantic rows, rather than from reviewed heldout-root packets alone.",
            "This package directly targets the two live boundary families: evidence citation and verifier outcome, while preserving some surrounding localization and patch-impact context from the root-split base.",
            "It is still a train-support package, not a new headline eval surface.",
        ],
        "metrics": {
            "clean_rows": len(clean_rows),
            "clean_rows_by_language": counter(clean_rows, "language_family"),
            "clean_rows_by_task": counter(clean_rows, "task_type"),
            "clean_rows_by_objective": counter(clean_rows, "objective_family"),
            "clean_rows_by_source_stage": counter(clean_rows, "curriculum_source_stage"),
            "selected_test_anchor_rows": sum(1 for row in clean_rows if row.get("selected_test_anchor")),
            "verifier_anchor_rows": sum(1 for row in clean_rows if row.get("verifier_anchor")),
            "unique_source_roots": len({str(row.get("source_root_id") or row.get("source_bundle_id") or "") for row in clean_rows if str(row.get("source_root_id") or row.get("source_bundle_id") or "")}),
            "root_split_snapshot": root_split_summary.get("splits", {}).get("train"),
            "python_support_snapshot": python_summary.get("metrics"),
            "rust_clean_snapshot": rust_summary.get("metrics"),
        },
        "remaining_blockers": [
            "This package still inherits weak web supply because the underlying clean web source base remains tiny.",
            "Fresh heldout replenishment for evidence citation and Python verifier transition is still required before any new promotion claim.",
            "Rust clean support still comes from a narrow reviewed root set until more non-aliased Rust families are materialized.",
        ],
        "next_best_step": "Use this package as the next honest train-support source if another probe is required, or mine additional clean rows from the same root-split pipeline before training again.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "rows_jsonl": rel(ROWS_JSONL),
            "inventory_jsonl": rel(INVENTORY_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROWS_JSONL, clean_rows)
    write_jsonl(INVENTORY_JSONL, inventory(clean_rows))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
