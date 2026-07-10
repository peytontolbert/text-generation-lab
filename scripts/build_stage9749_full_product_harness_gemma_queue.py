#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9749
NAME = "stage9749_full_product_harness_gemma_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE = OUT_DIR / "full_product_harness_gemma_queue.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_PRODUCT_HARNESS_GEMMA_QUEUE_STAGE9749.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_PACKS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_multilingual_task_pack_skeleton.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage9684_v27_multilingual_eval_acceptance_contract/v27_multilingual_eval_acceptance_contract.json"
SOURCE_ANTI_HACK = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
SOURCE_STANDALONE_QUEUE = ROOT / "runs/local/artifacts/stage9748_supported_standalone_gemma_queue/supported_standalone_gemma_queue.json"


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


def pack_identity_hash(pack: dict[str, Any]) -> str:
    payload = {
        "task_pack_id": pack.get("task_pack_id"),
        "source_id": pack.get("source_id"),
        "lineage_hash": pack.get("lineage_hash"),
        "language_family": pack.get("language_family"),
        "skill_area": pack.get("skill_area"),
        "mode": pack.get("mode"),
        "slice_tags": pack.get("slice_tags"),
        "anti_cheat_requirements": pack.get("anti_cheat_requirements"),
        "required_evidence": pack.get("required_evidence"),
        "thresholds": pack.get("thresholds"),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_queue() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    packs_doc = load_json(SOURCE_PACKS)
    contract = load_json(SOURCE_CONTRACT)
    anti_hack = load_json(SOURCE_ANTI_HACK)
    standalone_queue = load_json(SOURCE_STANDALONE_QUEUE)

    packs = packs_doc.get("benchmark_packs") if isinstance(packs_doc.get("benchmark_packs"), list) else []
    harness_packs = [pack for pack in packs if pack.get("mode") == "full_product_harness"]
    standalone_entries = standalone_queue.get("queue_entries") if isinstance(standalone_queue.get("queue_entries"), list) else []
    standalone_by_pair = {
        (str(row.get("language_family") or ""), str(row.get("skill_area") or "")): row
        for row in standalone_entries
    }
    failures: list[str] = []
    queue_entries: list[dict[str, Any]] = []
    required_harness_evidence = contract.get("required_evidence_by_mode", {}).get("full_product_harness")
    for pack in harness_packs:
        language = str(pack.get("language_family") or "")
        skill = str(pack.get("skill_area") or "")
        proxy = standalone_by_pair.get((language, skill))
        proxy_score = None if not proxy else float(proxy.get("priority_score") or 0.0)
        queue_entries.append({
            "cell_key": f"full_product_harness::{language}::{skill}",
            "task_pack_id": pack.get("task_pack_id"),
            "source_id": pack.get("source_id"),
            "lineage_hash": pack.get("lineage_hash"),
            "language_family": language,
            "skill_area": skill,
            "pack_identity_hash": pack_identity_hash(pack),
            "required_evidence": list(pack.get("required_evidence") or []),
            "anti_cheat_requirements": list(pack.get("anti_cheat_requirements") or []),
            "thresholds": dict(pack.get("thresholds") or {}),
            "anti_eval_hacking_gate_passed": anti_hack.get("passed") is True,
            "same_harness_prompt_surface_required": "same_harness_prompt_surface_for_100m_and_gemma" in (pack.get("anti_cheat_requirements") or []),
            "proxy_standalone_cell_key": None if not proxy else str(proxy.get("cell_key") or ""),
            "proxy_standalone_priority_score": proxy_score,
            "priority_bucket": "aligned_with_supported_standalone_cell" if proxy else "no_standalone_proxy_support_yet",
            "ready_for_harness_when_authorized": anti_hack.get("passed") is True,
            "gemma_execution_authorized_now": False,
            "harness_execution_authorized_now": False,
            "remaining_blockers": [
                "same_task_pack_100m_vs_gemma12b_harness_evidence_missing",
                "harness_run_not_recorded",
                "tool_trace_spans_missing",
                "verifier_results_missing",
                "patch_minimality_or_abstain_scores_missing",
                "expert_maintainer_rubric_scores_missing",
                "anti_cheat_cards_not_attached_for_specific_cell",
            ],
        })
    queue_entries = sorted(
        queue_entries,
        key=lambda row: (
            0 if row["priority_bucket"] == "aligned_with_supported_standalone_cell" else 1,
            -(float(row["proxy_standalone_priority_score"]) if row["proxy_standalone_priority_score"] is not None else -1.0),
            str(row.get("language_family") or ""),
            str(row.get("skill_area") or ""),
        ),
    )
    for index, row in enumerate(queue_entries, start=1):
        row["priority_rank"] = index
    if not isinstance(required_harness_evidence, list):
        failures.append("missing_harness_required_evidence_contract")
    else:
        for row in queue_entries:
            if row["required_evidence"] != required_harness_evidence:
                failures.append(f"required_evidence_mismatch:{row['cell_key']}")
                break
    if anti_hack.get("passed") is not True:
        failures.append("stage9717_not_passed")
    if standalone_queue.get("passed") is not True:
        failures.append("stage9748_not_passed")
    if len(harness_packs) != 36:
        failures.append("harness_pack_count_not_36")
    if len(queue_entries) != 36:
        failures.append("queue_entry_count_not_36")
    metrics = {
        "queue_entries": len(queue_entries),
        "priority_buckets": dict(sorted(Counter(str(row.get("priority_bucket") or "") for row in queue_entries).items())),
        "languages": dict(sorted(Counter(str(row.get("language_family") or "") for row in queue_entries).items())),
        "skills": dict(sorted(Counter(str(row.get("skill_area") or "") for row in queue_entries).items())),
        "top_queue_entry": queue_entries[0]["cell_key"] if queue_entries else None,
        "top_priority_bucket": queue_entries[0]["priority_bucket"] if queue_entries else None,
        "top_proxy_standalone_cell_key": queue_entries[0]["proxy_standalone_cell_key"] if queue_entries else None,
    }
    return {
        "passed": not failures,
        "failures": failures,
        "queue_entries": queue_entries,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    queue = build_queue()
    QUEUE.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "When harness and Gemma execution are explicitly opened, start the full-product queue with the 13 cells "
        "aligned to supported standalone evidence, then cover the remaining 23 cells that still lack any current "
        "100M-side proxy support."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": queue["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **queue["metrics"]},
        "artifacts": {
            "queue": str(QUEUE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Packaged the 36 full-product harness acceptance cells into a Gemma comparison queue, prioritizing the 13 cells that already align to supported standalone evidence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9749 Full Product Harness Gemma Queue",
        "",
        f"Passed: `{summary['passed']}`",
        f"Queue entries: `{summary['metrics']['queue_entries']}`",
        f"Priority buckets: `{summary['metrics']['priority_buckets']}`",
        f"Languages: `{summary['metrics']['languages']}`",
        f"Skills: `{summary['metrics']['skills']}`",
        f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
        "",
        "This stage packages the full-product harness side of the v2.7 comparison problem. It does not run harness or Gemma, but it makes the full harness queue explicit and prioritizes the subset whose standalone analogues already have truthful 100M-side evidence.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "queue_entries": summary["metrics"]["queue_entries"],
        "priority_buckets": summary["metrics"]["priority_buckets"],
        "top_queue_entry": summary["metrics"]["top_queue_entry"],
        "failures": queue["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if queue["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
