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

try:
    from build_stage9719_multilingual_comparison_evidence_bundle_contract import (
        RUBRIC_SUBSKILLS,
        build_template as build_stage9719_template,
    )
except ModuleNotFoundError:
    from scripts.build_stage9719_multilingual_comparison_evidence_bundle_contract import (  # type: ignore
        RUBRIC_SUBSKILLS,
        build_template as build_stage9719_template,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9752
NAME = "stage9752_supported_standalone_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "supported_standalone_review_packets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORTED_STANDALONE_REVIEW_PACKETS_STAGE9752.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

QUEUE = ROOT / "runs/local/artifacts/stage9748_supported_standalone_gemma_queue/supported_standalone_gemma_queue.json"
TRUTHFUL = ROOT / "runs/local/artifacts/stage9747_truthful_standalone_acceptance_evidence_bridge/truthful_standalone_acceptance_evidence_bridge.json"
ANTI_HACK = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
ACCEPTANCE_LEDGER = ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


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


def template_output_paths(cell_key: str) -> dict[str, str]:
    slug = cell_key.replace("::", "__")
    base = OUT_DIR / "review_packets" / slug
    return {
        "packet_dir": str(base.relative_to(ROOT)),
        "expert_maintainer_rubric_scores": str((base / "expert_maintainer_rubric_review.json").relative_to(ROOT)),
        "anti_cheat_cards": str((base / "anti_cheat_review_card.json").relative_to(ROOT)),
        "same_prompt_surface_gemma12b_outputs": str((base / "same_prompt_surface_gemma12b_outputs.json").relative_to(ROOT)),
        "frozen_export_or_checkpoint_hash": str((base / "frozen_export_or_checkpoint_hash.txt").relative_to(ROOT)),
    }


def build_review_packets(
    queue: dict[str, Any],
    truthful: dict[str, Any],
    anti_hack: dict[str, Any],
    acceptance_ledger: dict[str, Any],
) -> dict[str, Any]:
    queue_entries = queue.get("queue_entries") if isinstance(queue.get("queue_entries"), list) else []
    truthful_records = truthful.get("records") if isinstance(truthful.get("records"), list) else []
    truthful_index = {str(row.get("cell_key") or ""): row for row in truthful_records}
    ledger_records = acceptance_ledger.get("records") if isinstance(acceptance_ledger.get("records"), list) else []
    ledger_index = {str(row.get("cell_key") or ""): row for row in ledger_records}
    challenge_records = anti_hack.get("challenge_matrix", {}).get("records") if isinstance(anti_hack.get("challenge_matrix"), dict) else []

    packets: list[dict[str, Any]] = []
    failures: list[str] = []
    for entry in queue_entries:
        cell_key = str(entry.get("cell_key") or "")
        truthful_record = truthful_index.get(cell_key)
        ledger_record = ledger_index.get(cell_key)
        if truthful_record is None:
            failures.append(f"missing_truthful_record:{cell_key}")
            continue
        if ledger_record is None:
            failures.append(f"missing_acceptance_record:{cell_key}")
            continue
        bundle = build_stage9719_template(ledger_record)
        packet_paths = template_output_paths(cell_key)
        same_surface = entry.get("same_surface_packet") if isinstance(entry.get("same_surface_packet"), dict) else {}
        supports = truthful_record.get("attached_evidence") if isinstance(truthful_record.get("attached_evidence"), list) else []
        evidence_ref = supports[0] if supports else {}

        bundle["same_surface_comparison"] = {
            "present": True,
            "prompt_surface_hash_100m": same_surface.get("surface_hash"),
            "prompt_surface_hash_gemma12b": None,
            "score_100m": same_surface.get("eval_exact"),
            "score_gemma12b": None,
            "scoring_constraints_hash": same_surface.get("surface_hash"),
            "same_surface_verified": False,
            "hundred_m_beats_gemma12b": False,
        }
        bundle["expert_maintainer_rubric"] = {
            "present": False,
            "rubric_version": "expert_maintainer_v1",
            "passed": False,
            "subskills": {name: None for name in RUBRIC_SUBSKILLS},
            "failure_trace_refs": [],
        }
        bundle["anti_cheat_attachment"] = {
            "present": False,
            "stage9717_gate_passed": anti_hack.get("passed") is True,
            "passed": False,
            "anti_cheat_card_paths": [packet_paths["anti_cheat_cards"]],
        }
        bundle["evidence_artifacts"] = {
            "frozen_export_or_checkpoint_hash": None,
            "standalone_generation_or_structured_action_outputs": None,
            "same_prompt_surface_gemma12b_outputs": None,
            "language_slice_scores": evidence_ref.get("path"),
            "expert_maintainer_rubric_scores": None,
            "anti_cheat_cards": None,
            "telemetry_bundle": evidence_ref.get("path"),
        }
        bundle["claim_ready_candidate"] = False
        bundle["notes"] = [
            "template_only_do_not_mark_claim_ready_without_real_evidence",
            "prefilled_with_truthful_100m_side_support",
            "gemma12b_side_and_expert_review_still_required",
        ]
        packet = {
            "cell_key": cell_key,
            "priority_rank": entry.get("priority_rank"),
            "priority_score": entry.get("priority_score"),
            "priority_reason": entry.get("priority_reason"),
            "language_family": entry.get("language_family"),
            "skill_area": entry.get("skill_area"),
            "task_pack_id": entry.get("task_pack_id"),
            "ready_for_gemma_when_authorized": entry.get("ready_for_gemma_when_authorized") is True,
            "review_packet_paths": packet_paths,
            "same_surface_packet": same_surface,
            "supporting_evidence_refs": supports,
            "global_anti_hack_gate": {
                "passed": anti_hack.get("passed") is True,
                "challenge_families": [
                    {
                        "challenge_family": row.get("challenge_family"),
                        "passed": row.get("passed") is True,
                        "required_requirements": row.get("required_requirements"),
                    }
                    for row in challenge_records
                ],
            },
            "expert_maintainer_review_template": {
                "rubric_version": "expert_maintainer_v1",
                "subskills_required": RUBRIC_SUBSKILLS,
                "must_pass_all_subskills": True,
                "failure_trace_refs_required_if_not_passed": True,
                "output_path": packet_paths["expert_maintainer_rubric_scores"],
            },
            "anti_cheat_review_template": {
                "must_pass_global_stage9717_gate": True,
                "must_attach_cell_specific_cards": True,
                "challenge_family_count": len(challenge_records),
                "challenge_families": [row.get("challenge_family") for row in challenge_records],
                "output_path": packet_paths["anti_cheat_cards"],
            },
            "same_surface_gemma_review_slot": {
                "required": True,
                "authorized_now": False,
                "output_path": packet_paths["same_prompt_surface_gemma12b_outputs"],
            },
            "checkpoint_hash_review_slot": {
                "required": True,
                "output_path": packet_paths["frozen_export_or_checkpoint_hash"],
            },
            "merge_ready_bundle_template": bundle,
        }
        packets.append(packet)

    metrics = {
        "queue_entries": len(queue_entries),
        "review_packets": len(packets),
        "languages": sorted({str(packet.get("language_family") or "") for packet in packets}),
        "skills": sorted({str(packet.get("skill_area") or "") for packet in packets}),
        "top_packet": packets[0]["cell_key"] if packets else None,
        "all_packets_ready_for_gemma_when_authorized": all(packet["ready_for_gemma_when_authorized"] for packet in packets),
        "review_packets_with_rubric_slots": sum(1 for packet in packets if packet["expert_maintainer_review_template"]["output_path"]),
        "review_packets_with_anticheat_slots": sum(1 for packet in packets if packet["anti_cheat_review_template"]["output_path"]),
        "review_packets_with_gemma_slots": sum(1 for packet in packets if packet["same_surface_gemma_review_slot"]["output_path"]),
        "challenge_family_count": len(challenge_records),
    }
    if metrics["queue_entries"] != 13:
        failures.append("queue_entries_not_13")
    if metrics["review_packets"] != 13:
        failures.append("review_packets_not_13")
    if metrics["languages"] != ["c_cpp", "python", "rust", "web_js_ts_html"]:
        failures.append("language_coverage_mismatch")
    if metrics["challenge_family_count"] != 6:
        failures.append("challenge_family_count_mismatch")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "review_packets": packets,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_review_packets(
        load_json(QUEUE),
        load_json(TRUTHFUL),
        load_json(ANTI_HACK),
        load_json(ACCEPTANCE_LEDGER),
    )
    write_jsonl(PACKETS, built["review_packets"])
    next_step = (
        "Fill the Stage9752 rubric and anti-cheat review slots for the 13 supported standalone cells, then execute the "
        "matching Gemma outputs into the reserved same-surface slots once runner authorization or recovery is available."
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
            "review_packets": str(PACKETS.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized prefilled expert-review and anti-cheat packet templates for the 13 supported standalone cells so human review and future Gemma comparison can attach to a uniform evidence surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9752 Supported Standalone Review Packets",
        "",
        f"Passed: `{summary['passed']}`",
        f"Review packets: `{summary['metrics']['review_packets']}`",
        f"Languages: `{summary['metrics']['languages']}`",
        f"Skills: `{summary['metrics']['skills']}`",
        f"Challenge families: `{summary['metrics']['challenge_family_count']}`",
        "",
        "This stage turns the 13 strongest standalone candidates into concrete review packets with prefilled 100M-side evidence, reserved output slots for Gemma outputs and checkpoint hashes, and explicit templates for expert-maintainer rubric review and cell-specific anti-cheat cards.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "review_packets": summary["metrics"]["review_packets"],
        "languages": summary["metrics"]["languages"],
        "skills": summary["metrics"]["skills"],
        "challenge_family_count": summary["metrics"]["challenge_family_count"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
