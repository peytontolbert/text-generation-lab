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
STAGE = 9765
NAME = "stage9765_standalone_review_evidence_drafts"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "standalone_review_evidence_drafts_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STANDALONE_REVIEW_EVIDENCE_DRAFTS_STAGE9765.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
STUB_MANIFEST = ROOT / "runs/local/artifacts/stage9753_supported_standalone_review_stub_files/supported_standalone_review_stub_manifest.json"
TRUTHFUL_QUEUE = ROOT / "runs/local/artifacts/stage9761_truthful_ready_now_execution_queue/truthful_ready_now_execution_queue.json"
HARNESS_PREP_AUDIT = ROOT / "runs/local/artifacts/stage9762_harness_prep_completion_audit/harness_prep_completion_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _anti_cheat_draft(packet: dict[str, Any]) -> dict[str, Any]:
    same_surface = packet.get("same_surface_packet") if isinstance(packet.get("same_surface_packet"), dict) else {}
    gate = packet.get("global_anti_hack_gate") if isinstance(packet.get("global_anti_hack_gate"), dict) else {}
    supporting = packet.get("supporting_evidence_refs") if isinstance(packet.get("supporting_evidence_refs"), list) else []
    refs = [row.get("path") for row in supporting if row.get("path")]
    return {
        "cell_key": packet.get("cell_key"),
        "status": "draft_evidence_ready_for_human_cell_specific_review",
        "auto_review_complete": False,
        "passed": False,
        "reviewer_must_confirm": True,
        "global_stage9717_gate_passed": gate.get("passed") is True,
        "same_surface_hash_100m": same_surface.get("surface_hash"),
        "same_surface_row_counts": same_surface.get("split_counts"),
        "same_surface_row_ids": same_surface.get("row_ids"),
        "supporting_evidence_paths": refs,
        "challenge_families": [
            {
                "challenge_family": row.get("challenge_family"),
                "global_gate_passed": row.get("passed") is True,
                "required_requirements": row.get("required_requirements"),
                "cell_specific_card_present": False,
                "passed": False,
                "cell_evidence_hints": [
                    "confirm the reviewed outputs use the same surface hash as the 100M packet",
                    "confirm no leakage or shortcutting is visible in the attached task pack and output surface",
                    "cite concrete examples or failure traces in reviewer notes",
                ],
                "reviewer_notes": [],
            }
            for row in gate.get("challenge_families") or []
        ],
        "reviewer_notes": [
            "This draft carries forward global anti-cheat requirements and cell-specific evidence anchors only.",
            "A human reviewer still must judge whether the concrete cell outputs satisfy each challenge family.",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }


def _rubric_draft(packet: dict[str, Any]) -> dict[str, Any]:
    same_surface = packet.get("same_surface_packet") if isinstance(packet.get("same_surface_packet"), dict) else {}
    template = packet.get("expert_maintainer_review_template") if isinstance(packet.get("expert_maintainer_review_template"), dict) else {}
    supporting = packet.get("supporting_evidence_refs") if isinstance(packet.get("supporting_evidence_refs"), list) else []
    refs = [row.get("path") for row in supporting if row.get("path")]
    hints = {
        "understands_user_intent": ["inspect task pack wording and 100M outputs against requested task"],
        "binds_symbols_correctly": ["inspect symbol-binding or edit-target rows in the attached surface evidence"],
        "localizes_edit_scope": ["inspect whether outputs stay within the row-local target region"],
        "chooses_minimal_edit_operator": ["inspect patch operator choice or abstain behavior"],
        "predicts_verifier_command": ["inspect verifier-facing surfaces where applicable"],
        "interprets_verifier_failure": ["inspect repair evidence and failure-trace references where applicable"],
        "repairs_or_abstains_safely": ["inspect whether the model repairs valid issues or abstains without unsafe invention"],
        "keeps_patch_minimal": ["inspect whether edits stay narrow and avoid broad rewrites"],
        "avoids_hallucinated_symbols": ["inspect outputs for invented identifiers or unsupported references"],
        "produces_contentful_final_answer": ["inspect whether outputs are non-empty and task-relevant"],
    }
    return {
        "cell_key": packet.get("cell_key"),
        "status": "draft_evidence_ready_for_human_rubric_review",
        "auto_review_complete": False,
        "passed": False,
        "reviewer_must_confirm": True,
        "rubric_version": template.get("rubric_version"),
        "must_pass_all_subskills": template.get("must_pass_all_subskills") is True,
        "source_100m_score": packet.get("priority_score"),
        "same_surface_hash_100m": same_surface.get("surface_hash"),
        "same_surface_row_counts": same_surface.get("split_counts"),
        "same_surface_row_ids": same_surface.get("row_ids"),
        "supporting_evidence_paths": refs,
        "subskills": {
            name: {
                "judgment": None,
                "reviewer_notes": [],
                "evidence_hints": hints.get(name, ["review attached source evidence for this subskill"]),
            }
            for name in template.get("subskills_required") or []
        },
        "reviewer_notes": [
            "This draft only preloads evidence anchors and subskill-specific review hints.",
            "A human reviewer still must assign subskill judgments and attach failure traces when not passed.",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }


def build_drafts(
    packets: list[dict[str, Any]],
    stub_manifest: dict[str, Any],
    truthful_queue: dict[str, Any],
    harness_prep_audit: dict[str, Any],
) -> dict[str, Any]:
    stub_rows = stub_manifest.get("rows") if isinstance(stub_manifest.get("rows"), list) else []
    stub_index = {str(row.get("cell_key") or ""): row for row in stub_rows}
    queue_rows = truthful_queue.get("queue_entries") if isinstance(truthful_queue.get("queue_entries"), list) else []
    standalone_queue = [row for row in queue_rows if row.get("front") == "standalone"]
    harness_metrics = harness_prep_audit.get("metrics") if isinstance(harness_prep_audit.get("metrics"), dict) else {}

    failures: list[str] = []
    manifest_rows: list[dict[str, Any]] = []
    for packet in packets:
        cell_key = str(packet.get("cell_key") or "")
        stub = stub_index.get(cell_key)
        if stub is None:
            failures.append(f"missing_stub_manifest_row:{cell_key}")
            continue
        slug = cell_key.replace("::", "__")
        base = OUT_DIR / "review_drafts" / slug
        rubric_path = base / "expert_maintainer_review_evidence_draft.json"
        anti_cheat_path = base / "anti_cheat_review_evidence_draft.json"
        _write_json(rubric_path, _rubric_draft(packet))
        _write_json(anti_cheat_path, _anti_cheat_draft(packet))
        manifest_rows.append({
            "cell_key": cell_key,
            "priority_rank": packet.get("priority_rank"),
            "language_family": packet.get("language_family"),
            "skill_area": packet.get("skill_area"),
            "existing_rubric_stub": stub.get("expert_maintainer_rubric_scores"),
            "existing_anti_cheat_stub": stub.get("anti_cheat_cards"),
            "draft_rubric_path": str(rubric_path.relative_to(ROOT)),
            "draft_anti_cheat_path": str(anti_cheat_path.relative_to(ROOT)),
        })

    metrics = {
        "supported_cells": len(packets),
        "draft_rows": len(manifest_rows),
        "remaining_standalone_review_tasks": len(standalone_queue),
        "harness_ready_now_after_prep_completion": int(harness_metrics.get("remaining_harness_entries_after_completion") or 0),
        "draft_rubric_files": len(manifest_rows),
        "draft_anti_cheat_files": len(manifest_rows),
        "top_queue_entry": standalone_queue[0]["cell_key"] + "::" + standalone_queue[0]["task"] if standalone_queue else None,
    }
    if metrics["supported_cells"] != 13:
        failures.append("supported_cells_not_13")
    if metrics["draft_rows"] != 13:
        failures.append("draft_rows_not_13")
    if metrics["remaining_standalone_review_tasks"] != 26:
        failures.append("remaining_standalone_review_tasks_not_26")
    if metrics["harness_ready_now_after_prep_completion"] != 0:
        failures.append("harness_ready_now_after_prep_completion_not_0")

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
    built = build_drafts(
        load_jsonl(SOURCE_PACKETS),
        load_json(STUB_MANIFEST),
        load_json(TRUTHFUL_QUEUE),
        load_json(HARNESS_PREP_AUDIT),
    )
    MANIFEST.write_text(json.dumps({
        "stage": STAGE,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "rows": built["rows"],
        "authority": dict(AUTHORITY_CLOSED),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the Stage9765 draft review files to work the remaining 26 standalone review tasks in order, starting with "
        "python symbol-binding, while keeping Gemma execution and checkpoint/hash attachment closed until real external evidence exists."
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
        "decision": "Materialized evidence-backed draft rubric and anti-cheat review files for the 13 supported standalone cells so reviewers can work from actual hashes, row sets, evidence paths, and challenge requirements rather than empty placeholders.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9765 Standalone Review Evidence Drafts",
        "",
        f"Passed: `{summary['passed']}`",
        f"Supported cells: `{summary['metrics']['supported_cells']}`",
        f"Remaining standalone review tasks: `{summary['metrics']['remaining_standalone_review_tasks']}`",
        f"Draft rubric files: `{summary['metrics']['draft_rubric_files']}`",
        f"Draft anti-cheat files: `{summary['metrics']['draft_anti_cheat_files']}`",
        f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
        "",
        "This stage does not claim that human review is finished. It upgrades the review surface from blank placeholders to evidence-backed drafts containing same-surface hashes, row sets, supporting evidence paths, subskill review hints, and anti-cheat challenge requirements.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "supported_cells": summary["metrics"]["supported_cells"],
        "remaining_standalone_review_tasks": summary["metrics"]["remaining_standalone_review_tasks"],
        "draft_rubric_files": summary["metrics"]["draft_rubric_files"],
        "draft_anti_cheat_files": summary["metrics"]["draft_anti_cheat_files"],
        "top_queue_entry": summary["metrics"]["top_queue_entry"],
        "failures": built["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
