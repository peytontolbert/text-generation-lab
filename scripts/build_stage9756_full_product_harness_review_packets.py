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
STAGE = 9756
NAME = "stage9756_full_product_harness_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "full_product_harness_review_packets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_PRODUCT_HARNESS_REVIEW_PACKETS_STAGE9756.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

QUEUE = ROOT / "runs/local/artifacts/stage9749_full_product_harness_gemma_queue/full_product_harness_gemma_queue.json"
RUNBOOK = ROOT / "runs/local/artifacts/stage9750_deferred_comparison_execution_runbook/deferred_comparison_execution_runbook.json"


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
        "harness_run_id": str((base / "harness_run_id.txt").relative_to(ROOT)),
        "same_task_pack_as_gemma12b": str((base / "same_task_pack_as_gemma12b.json").relative_to(ROOT)),
        "tool_trace_spans": str((base / "tool_trace_spans.jsonl").relative_to(ROOT)),
        "verifier_results": str((base / "verifier_results.json").relative_to(ROOT)),
        "patch_minimality_or_abstain_scores": str((base / "patch_minimality_or_abstain_scores.json").relative_to(ROOT)),
        "expert_maintainer_rubric_scores": str((base / "expert_maintainer_rubric_review.json").relative_to(ROOT)),
        "anti_cheat_cards": str((base / "anti_cheat_review_card.json").relative_to(ROOT)),
    }


def build_review_packets(queue: dict[str, Any], runbook: dict[str, Any]) -> dict[str, Any]:
    entries = queue.get("queue_entries") if isinstance(queue.get("queue_entries"), list) else []
    runner_status = runbook.get("execution_fronts", {}).get("full_product_harness_comparison", {}).get("runner_status")
    packets: list[dict[str, Any]] = []
    failures: list[str] = []
    for entry in entries:
        record = {
            "cell_key": entry.get("cell_key"),
            "task_pack_id": entry.get("task_pack_id"),
            "source_id": entry.get("source_id"),
            "mode": "full_product_harness",
            "language_family": entry.get("language_family"),
            "skill_area": entry.get("skill_area"),
            "required_evidence": entry.get("required_evidence"),
        }
        bundle = build_stage9719_template(record)
        packet_paths = template_output_paths(str(entry.get("cell_key") or ""))
        bundle["same_surface_comparison"] = {
            "present": False,
            "prompt_surface_hash_100m": None,
            "prompt_surface_hash_gemma12b": None,
            "score_100m": None,
            "score_gemma12b": None,
            "scoring_constraints_hash": entry.get("pack_identity_hash"),
            "same_surface_verified": False,
            "hundred_m_beats_gemma12b": False,
        }
        bundle["anti_cheat_attachment"] = {
            "present": False,
            "stage9717_gate_passed": entry.get("anti_eval_hacking_gate_passed") is True,
            "passed": False,
            "anti_cheat_card_paths": [packet_paths["anti_cheat_cards"]],
        }
        bundle["expert_maintainer_rubric"] = {
            "present": False,
            "rubric_version": "expert_maintainer_v1",
            "passed": False,
            "subskills": {name: None for name in RUBRIC_SUBSKILLS},
            "failure_trace_refs": [],
        }
        bundle["evidence_artifacts"] = {
            "harness_run_id": None,
            "same_task_pack_as_gemma12b": None,
            "tool_trace_spans": None,
            "verifier_results": None,
            "patch_minimality_or_abstain_scores": None,
            "expert_maintainer_rubric_scores": None,
            "anti_cheat_cards": None,
        }
        bundle["claim_ready_candidate"] = False
        bundle["notes"] = [
            "template_only_do_not_mark_claim_ready_without_real_harness_evidence",
            "full_product_runner_surface_still_missing",
        ]
        packets.append({
            "cell_key": entry.get("cell_key"),
            "priority_rank": entry.get("priority_rank"),
            "priority_bucket": entry.get("priority_bucket"),
            "proxy_standalone_cell_key": entry.get("proxy_standalone_cell_key"),
            "proxy_standalone_priority_score": entry.get("proxy_standalone_priority_score"),
            "language_family": entry.get("language_family"),
            "skill_area": entry.get("skill_area"),
            "ready_for_harness_when_authorized": entry.get("ready_for_harness_when_authorized") is True,
            "runner_status": runner_status,
            "review_packet_paths": packet_paths,
            "harness_execution_template": {
                "required": True,
                "runner_status": runner_status,
                "required_artifacts": entry.get("required_evidence"),
            },
            "expert_maintainer_review_template": {
                "rubric_version": "expert_maintainer_v1",
                "subskills_required": RUBRIC_SUBSKILLS,
                "must_pass_all_subskills": True,
                "failure_trace_refs_required_if_not_passed": True,
                "output_path": packet_paths["expert_maintainer_rubric_scores"],
            },
            "anti_cheat_review_template": {
                "must_attach_cell_specific_cards": True,
                "must_pass_global_stage9717_gate": entry.get("anti_eval_hacking_gate_passed") is True,
                "challenge_requirements": entry.get("anti_cheat_requirements"),
                "output_path": packet_paths["anti_cheat_cards"],
            },
            "merge_ready_bundle_template": bundle,
        })

    metrics = {
        "queue_entries": len(entries),
        "review_packets": len(packets),
        "languages": sorted({str(packet.get("language_family") or "") for packet in packets}),
        "skills": sorted({str(packet.get("skill_area") or "") for packet in packets}),
        "priority_buckets": dict(sorted((queue.get("metrics", {}).get("priority_buckets") or {}).items())),
        "top_packet": packets[0]["cell_key"] if packets else None,
        "review_packets_with_harness_slots": sum(1 for packet in packets if packet["harness_execution_template"]["required"]),
        "review_packets_with_rubric_slots": sum(1 for packet in packets if packet["expert_maintainer_review_template"]["output_path"]),
        "review_packets_with_anticheat_slots": sum(1 for packet in packets if packet["anti_cheat_review_template"]["output_path"]),
    }
    if metrics["queue_entries"] != 36:
        failures.append("queue_entries_not_36")
    if metrics["review_packets"] != 36:
        failures.append("review_packets_not_36")
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
    built = build_review_packets(load_json(QUEUE), load_json(RUNBOOK))
    write_jsonl(PACKETS, built["review_packets"])
    next_step = (
        "Use the Stage9756 packet paths to prepare rubric and anti-cheat review artifacts for all 36 harness cells, then populate "
        "the reserved harness execution artifacts once a concrete full-product runner surface is recovered or authorized."
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
        "decision": "Materialized harness review packets with reserved artifact paths for all required full-product evidence so the 36-cell harness frontier has the same operational shape as the standalone frontier.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9756 Full Product Harness Review Packets",
        "",
        f"Passed: `{summary['passed']}`",
        f"Review packets: `{summary['metrics']['review_packets']}`",
        f"Languages: `{summary['metrics']['languages']}`",
        f"Skills: `{summary['metrics']['skills']}`",
        f"Priority buckets: `{summary['metrics']['priority_buckets']}`",
        "",
        "This stage gives each harness cell a stable packet directory and reserved artifact paths for harness run identity, same-task-pack Gemma comparison, tool traces, verifier results, patch-minimality scores, expert rubric review, and anti-cheat review.",
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
        "top_packet": summary["metrics"]["top_packet"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
