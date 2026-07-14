#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10979
NAME = "stage10979_reviewed_evidence_role_curriculum_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "reviewed_evidence_role_curriculum_package.json"
ALL_ROWS_JSONL = OUT_DIR / "support_rows_all.jsonl"
CLEAN_ROWS_JSONL = OUT_DIR / "support_rows_clean.jsonl"
OVERLAP_ROWS_JSONL = OUT_DIR / "support_rows_overlap_or_stress.jsonl"
INVENTORY_JSONL = OUT_DIR / "curriculum_inventory.jsonl"

SEMANTIC_SUMMARY = ARTIFACTS / "stage10925_reviewed_evidence_role_semantic_support_package" / "reviewed_evidence_role_semantic_support_package.json"
SEMANTIC_ROWS = ARTIFACTS / "stage10925_reviewed_evidence_role_semantic_support_package" / "support_rows.jsonl"
REPLENISH_SUMMARY = ARTIFACTS / "stage10974_multilingual_reviewed_replenishment_package" / "multilingual_reviewed_replenishment_package.json"
REPLENISH_ROWS = ARTIFACTS / "stage10974_multilingual_reviewed_replenishment_package" / "train_support_rows.jsonl"
BASE_VALIDATION = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package" / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package" / "agentkernel_lite_encdec_strict_eval.jsonl"


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


def sanitize_train_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    return updated


def overlay_root_ids() -> set[str]:
    roots: set[str] = set()
    for row in load_jsonl(BASE_VALIDATION) + load_jsonl(BASE_STRICT):
        root_id = str(row.get("source_root_id") or row.get("source_bundle_id") or "")
        if root_id:
            roots.add(root_id)
    return roots


def classify_row(row: dict[str, Any], *, source_name: str, heldout_roots: set[str]) -> dict[str, Any]:
    updated = sanitize_train_row(row)
    source_root_id = str(updated.get("source_root_id") or updated.get("source_bundle_id") or "")
    split_role = str(updated.get("split_role") or "")
    anti_cheat = dict(updated.get("anti_cheat") or {})
    repo_overlap_stress = bool(
        anti_cheat.get("repo_overlap_stress_only")
        or anti_cheat.get("stress_overlap_only")
        or "stress" in split_role
    )
    overlaps_overlay_heldout = source_root_id in heldout_roots if source_root_id else False
    curriculum_bucket = "clean_train_support"
    if overlaps_overlay_heldout or repo_overlap_stress:
        curriculum_bucket = "overlap_or_stress_only"
    anti_cheat["curriculum_bucket"] = curriculum_bucket
    anti_cheat["overlay_heldout_overlap"] = overlaps_overlay_heldout
    anti_cheat["repo_overlap_stress_only"] = repo_overlap_stress
    updated["anti_cheat"] = anti_cheat
    updated["curriculum_source_stage"] = source_name
    updated["curriculum_bucket"] = curriculum_bucket
    updated["overlay_heldout_overlap"] = overlaps_overlay_heldout
    updated["repo_overlap_stress_only"] = repo_overlap_stress
    return updated


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("row_id") or ""),
            str(row.get("target_text") or ""),
            str(row.get("curriculum_source_stage") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def build_inventory(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for row in rows:
        inventory.append(
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
                "curriculum_bucket": row.get("curriculum_bucket"),
                "overlay_heldout_overlap": bool(row.get("overlay_heldout_overlap")),
                "repo_overlap_stress_only": bool(row.get("repo_overlap_stress_only")),
            }
        )
    inventory.sort(key=lambda item: (str(item.get("curriculum_bucket") or ""), str(item.get("language_family") or ""), str(item.get("row_id") or "")))
    return inventory


def counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    heldout_roots = overlay_root_ids()
    semantic_rows = [
        classify_row(row, source_name="stage10925_semantic", heldout_roots=heldout_roots)
        for row in load_jsonl(SEMANTIC_ROWS)
    ]
    replenish_rows = [
        classify_row(row, source_name="stage10974_replenishment", heldout_roots=heldout_roots)
        for row in load_jsonl(REPLENISH_ROWS)
    ]
    all_rows = dedupe_rows(semantic_rows + replenish_rows)
    clean_rows = [row for row in all_rows if str(row.get("curriculum_bucket") or "") == "clean_train_support"]
    overlap_rows = [row for row in all_rows if str(row.get("curriculum_bucket") or "") != "clean_train_support"]
    inventory = build_inventory(all_rows)

    semantic_summary = load_json(SEMANTIC_SUMMARY)
    replenish_summary = load_json(REPLENISH_SUMMARY)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(all_rows),
        "decision": "reviewed_evidence_role_curriculum_packaged_with_clean_vs_overlap_split",
        "claim_scope": [
            "Combine the clean reviewed evidence-role support sources into one curriculum inventory instead of another tiny scorer-tuning probe.",
            "Separate reusable clean train-support rows from overlap/stress-only rows so later probes can preserve honesty while still exploiting known stress material deliberately.",
        ],
        "source_artifacts": {
            "semantic_support_summary": rel(SEMANTIC_SUMMARY),
            "semantic_support_rows": rel(SEMANTIC_ROWS),
            "reviewed_replenishment_summary": rel(REPLENISH_SUMMARY),
            "reviewed_replenishment_rows": rel(REPLENISH_ROWS),
            "overlay_validation_rows": rel(BASE_VALIDATION),
            "overlay_strict_rows": rel(BASE_STRICT),
        },
        "headline_findings": [
            "The current evidence lane no longer needs another micro-tuning branch to identify data supply; the reviewed semantic and explicit-ledger branches can be merged into one curriculum source now.",
            "This package isolates overlap/stress rows so they can remain diagnostic rather than silently entering a promotable train-support path.",
            "Web remains present only through overlap/stress semantic support because there is still no pure-web selected-test heldout replenishment family.",
        ],
        "metrics": {
            "all_rows": len(all_rows),
            "clean_train_support_rows": len(clean_rows),
            "overlap_or_stress_rows": len(overlap_rows),
            "rows_by_source_stage": counter(all_rows, "curriculum_source_stage"),
            "all_rows_by_language": counter(all_rows, "language_family"),
            "clean_rows_by_language": counter(clean_rows, "language_family"),
            "overlap_rows_by_language": counter(overlap_rows, "language_family"),
            "all_rows_by_objective": counter(all_rows, "objective_family"),
            "clean_rows_by_objective": counter(clean_rows, "objective_family"),
            "all_rows_by_target": dict(sorted(Counter(str((row.get("standalone_projection_source") or {}).get("gold_value") or row.get("target_text") or "unknown") for row in all_rows).items())),
            "clean_rows_with_selected_test_anchor": sum(1 for row in clean_rows if row.get("selected_test_anchor")),
            "overlap_rows_with_selected_test_anchor": sum(1 for row in overlap_rows if row.get("selected_test_anchor")),
            "unique_source_roots_all": len({str(row.get("source_root_id") or row.get("source_bundle_id") or "") for row in all_rows if str(row.get("source_root_id") or row.get("source_bundle_id") or "")}),
            "unique_source_roots_clean": len({str(row.get("source_root_id") or row.get("source_bundle_id") or "") for row in clean_rows if str(row.get("source_root_id") or row.get("source_bundle_id") or "")}),
            "semantic_snapshot": semantic_summary.get("rows_by_language"),
            "replenishment_snapshot": replenish_summary.get("metrics"),
        },
        "remaining_blockers": [
            "This stage expands reviewed support geometry, not heldout size; it does not create new promotable strict rows by itself.",
            "Web still lacks a pure-web selected-test or verifier-anchored replenishment family, so its rows stay overlap/stress only here.",
            "Rust still needs fresh non-aliased heldout replenishment beyond the support-only reviewed bundles already included.",
        ],
        "next_best_step": "Use support_rows_clean.jsonl as the honest larger evidence-role train-support source for the next package stage, and keep support_rows_overlap_or_stress.jsonl gated for diagnostic or explicit stress use only.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "all_rows_jsonl": rel(ALL_ROWS_JSONL),
            "clean_rows_jsonl": rel(CLEAN_ROWS_JSONL),
            "overlap_rows_jsonl": rel(OVERLAP_ROWS_JSONL),
            "inventory_jsonl": rel(INVENTORY_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(ALL_ROWS_JSONL, all_rows)
    write_jsonl(CLEAN_ROWS_JSONL, clean_rows)
    write_jsonl(OVERLAP_ROWS_JSONL, overlap_rows)
    write_jsonl(INVENTORY_JSONL, inventory)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
