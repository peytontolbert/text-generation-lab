#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9767
NAME = "stage9767_enriched_standalone_review_targets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "enriched_standalone_review_targets_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ENRICHED_STANDALONE_REVIEW_TARGETS_STAGE9767.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

WORKBOOK = ROOT / "runs/local/artifacts/stage9766_standalone_review_execution_workbook/standalone_review_execution_workbook.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(rel_path: str) -> dict[str, Any]:
    return json.loads((ROOT / rel_path).read_text(encoding="utf-8"))


def _write_json(rel_path: str, payload: dict[str, Any]) -> None:
    path = ROOT / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _enrich_rubric(target: dict[str, Any], draft: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(target)
    enriched["evidence_draft_path"] = row.get("draft_artifact_path")
    enriched["required_human_action"] = row.get("required_human_action")
    enriched["same_surface_hash_100m"] = row.get("same_surface_hash_100m")
    enriched["same_surface_split_counts"] = row.get("same_surface_split_counts")
    enriched["same_surface_eval_exact"] = row.get("same_surface_eval_exact")
    enriched["same_surface_strict_exact"] = row.get("same_surface_strict_exact")
    enriched["supporting_evidence_paths"] = row.get("supporting_evidence_paths")
    enriched["packet_dir"] = row.get("packet_dir")
    enriched["reviewer_must_confirm"] = True
    enriched["auto_review_complete"] = False
    enriched["reviewer_guidance"] = draft.get("reviewer_notes")
    subskills = enriched.get("subskills")
    draft_subskills = draft.get("subskills") if isinstance(draft.get("subskills"), dict) else {}
    if isinstance(subskills, dict):
        enriched["subskill_evidence_hints"] = {
            name: details.get("evidence_hints")
            for name, details in draft_subskills.items()
            if isinstance(details, dict)
        }
    return enriched


def _enrich_anti_cheat(target: dict[str, Any], draft: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(target)
    enriched["evidence_draft_path"] = row.get("draft_artifact_path")
    enriched["required_human_action"] = row.get("required_human_action")
    enriched["same_surface_hash_100m"] = row.get("same_surface_hash_100m")
    enriched["same_surface_split_counts"] = row.get("same_surface_split_counts")
    enriched["same_surface_eval_exact"] = row.get("same_surface_eval_exact")
    enriched["same_surface_strict_exact"] = row.get("same_surface_strict_exact")
    enriched["supporting_evidence_paths"] = row.get("supporting_evidence_paths")
    enriched["packet_dir"] = row.get("packet_dir")
    enriched["reviewer_must_confirm"] = True
    enriched["auto_review_complete"] = False
    enriched["reviewer_guidance"] = draft.get("reviewer_notes")
    target_families = enriched.get("challenge_families")
    draft_families = draft.get("challenge_families") if isinstance(draft.get("challenge_families"), list) else []
    draft_index = {
        str(item.get("challenge_family") or ""): item
        for item in draft_families
        if isinstance(item, dict)
    }
    if isinstance(target_families, list):
        merged: list[dict[str, Any]] = []
        for family in target_families:
            if not isinstance(family, dict):
                continue
            name = str(family.get("challenge_family") or "")
            source = draft_index.get(name, {})
            merged.append({
                **family,
                "required_requirements": source.get("required_requirements"),
                "cell_evidence_hints": source.get("cell_evidence_hints"),
                "global_gate_passed": source.get("global_gate_passed"),
            })
        enriched["challenge_families"] = merged
    return enriched


def enrich_targets(workbook: dict[str, Any]) -> dict[str, Any]:
    rows = workbook.get("rows") if isinstance(workbook.get("rows"), list) else []
    manifest_rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for row in rows:
        draft_path = str(row.get("draft_artifact_path") or "")
        target_path = str(row.get("target_stub_path") or "")
        task = str(row.get("task") or "")
        if not draft_path or not target_path:
            failures.append(f"missing_paths:{row.get('cell_key')}")
            continue
        draft = _read_json(draft_path)
        target = _read_json(target_path)
        if task == "expert_maintainer_rubric_review":
            enriched = _enrich_rubric(target, draft, row)
        elif task == "cell_specific_anti_cheat_review":
            enriched = _enrich_anti_cheat(target, draft, row)
        else:
            failures.append(f"unexpected_task:{task}")
            continue
        _write_json(target_path, enriched)
        manifest_rows.append({
            "queue_position": row.get("queue_position"),
            "cell_key": row.get("cell_key"),
            "task": task,
            "draft_artifact_path": draft_path,
            "target_stub_path": target_path,
            "same_surface_hash_100m": row.get("same_surface_hash_100m"),
        })

    manifest_rows.sort(key=lambda row: int(row.get("queue_position") or 9999))
    metrics = {
        "enriched_tasks": len(manifest_rows),
        "rubric_targets_enriched": sum(1 for row in manifest_rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_targets_enriched": sum(1 for row in manifest_rows if row["task"] == "cell_specific_anti_cheat_review"),
        "unique_cells": len({row["cell_key"] for row in manifest_rows}),
        "top_queue_entry": manifest_rows[0]["cell_key"] + "::" + manifest_rows[0]["task"] if manifest_rows else None,
    }
    if metrics["enriched_tasks"] != 26:
        failures.append("enriched_tasks_not_26")
    if metrics["rubric_targets_enriched"] != 13:
        failures.append("rubric_targets_enriched_not_13")
    if metrics["anti_cheat_targets_enriched"] != 13:
        failures.append("anti_cheat_targets_enriched_not_13")
    if metrics["unique_cells"] != 13:
        failures.append("unique_cells_not_13")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "rows": manifest_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = enrich_targets(load_json(WORKBOOK))
    MANIFEST.write_text(json.dumps({
        "stage": STAGE,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "rows": built["rows"],
        "authority": dict(AUTHORITY_CLOSED),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Reviewers can now work directly in the tracked Stage9752 target files because they contain the Stage9765/9766 evidence anchors in place; continue down the 26-task queue starting with python symbol-binding."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **built["metrics"],
        },
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Enriched the tracked standalone rubric and anti-cheat target files in place with evidence draft paths, same-surface hashes and scores, packet links, supporting evidence references, and reviewer guidance while preserving human-owned judgment fields.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9767 Enriched Standalone Review Targets",
        "",
        f"Passed: `{summary['passed']}`",
        f"Enriched tasks: `{summary['metrics']['enriched_tasks']}`",
        f"Rubric targets enriched: `{summary['metrics']['rubric_targets_enriched']}`",
        f"Anti-cheat targets enriched: `{summary['metrics']['anti_cheat_targets_enriched']}`",
        f"Unique cells: `{summary['metrics']['unique_cells']}`",
        f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
        "",
        "This stage keeps the tracked review target files as the single place to finish judgments, but it no longer leaves them blank. The files now embed the same evidence anchors that were previously only available through separate draft artifacts and workbook rows.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "enriched_tasks": summary["metrics"]["enriched_tasks"],
        "rubric_targets_enriched": summary["metrics"]["rubric_targets_enriched"],
        "anti_cheat_targets_enriched": summary["metrics"]["anti_cheat_targets_enriched"],
        "unique_cells": summary["metrics"]["unique_cells"],
        "top_queue_entry": summary["metrics"]["top_queue_entry"],
        "failures": built["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
