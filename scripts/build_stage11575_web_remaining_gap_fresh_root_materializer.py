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
STAGE = 11575
NAME = "stage11575_web_remaining_gap_fresh_root_materializer"
OUT = ART / NAME
SUMMARY = OUT / "web_remaining_gap_fresh_root_materializer.json"
SUPPLY = OUT / "web_remaining_gap_candidate_supply.jsonl"
ADMISSION = OUT / "web_remaining_gap_admission_results.jsonl"

STAGE11574 = ART / "stage11574_web_remaining_gap_materialization_request/web_remaining_gap_work_items.jsonl"
STAGE11566 = ART / "stage11566_web_non_evidence_support_supply_inventory/web_non_evidence_support_candidates.jsonl"
STAGE11550 = ART / "stage11550_web_root_support_from_stage11507_probe_request/web_root_support_from_stage11507_probe_manifest.jsonl"
STAGE11530 = ART / "stage11530_web_new_family_materialization_packets/web_new_family_root_packets.jsonl"
STAGE11529 = ART / "stage11529_web_materialization_queue/web_materialization_work_items.jsonl"


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


def norm_repo_family(row: dict[str, Any]) -> str:
    return str(
        row.get("stage11566_repo_family")
        or row.get("repo_family")
        or row.get("git_repo_family")
        or row.get("repo_bucket")
        or "unknown"
    )


def norm_git_family(row: dict[str, Any]) -> str:
    return str(row.get("git_repo_family") or row.get("repo_family") or norm_repo_family(row))


def norm_root(row: dict[str, Any]) -> str:
    return str(row.get("stage11566_root_id") or row.get("root_id") or row.get("source_bundle_id") or row.get("bundle_id") or row.get("row_id"))


def norm_task(row: dict[str, Any]) -> str:
    return str(row.get("stage11566_task_type") or row.get("task_type") or "unknown")


def has_verifier_anchor(row: dict[str, Any]) -> bool:
    text = str(row.get("input_text") or row.get("prompt_text") or "").lower()
    if "selected verifier" in text or "verifier transition" in text or "focused test" in text or "executed test" in text:
        return True
    options = (row.get("standalone_projection_source") or {}).get("opaque_options") or row.get("opaque_options") or []
    return any("test" in str(opt.get("text") or opt.get("value") or "").lower() for opt in options)


def has_evidence_roles(row: dict[str, Any]) -> bool:
    text = str(row.get("input_text") or row.get("prompt_text") or "").lower()
    roles = ["candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path", "insufficient_evidence"]
    return sum(1 for role in roles if role in text) >= 2


def candidate_from_row(row: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "candidate_id": f"{source}::{norm_root(row)}::{norm_task(row)}",
        "source": source,
        "row_id": row.get("row_id"),
        "root_id": norm_root(row),
        "repo_family": norm_repo_family(row),
        "git_repo_family": norm_git_family(row),
        "task_type": norm_task(row),
        "has_verifier_anchor": has_verifier_anchor(row),
        "has_evidence_roles": has_evidence_roles(row),
        "target_text": row.get("target_text") or row.get("decoder_text"),
        "train_support_only": bool(row.get("train_support_only", True)),
        "strict_eval_eligible": bool(row.get("strict_eval_eligible", False)),
        "prompt_preview": str(row.get("input_text") or row.get("prompt_text") or "")[:600],
    }


def candidate_from_packet(row: dict[str, Any], source: str) -> dict[str, Any]:
    missing = list(row.get("missing_for_train_admission") or row.get("materialization_blockers") or [])
    return {
        "candidate_id": f"{source}::{row.get('root_id') or row.get('source_candidate_id')}",
        "source": source,
        "row_id": row.get("review_item_id") or row.get("source_candidate_id"),
        "root_id": str(row.get("root_id") or row.get("source_candidate_id")),
        "repo_family": str(row.get("repo_family") or "unknown"),
        "git_repo_family": str(row.get("git_repo_family") or row.get("repo_family") or "unknown"),
        "task_type": "root_packet",
        "has_verifier_anchor": bool(row.get("selected_verifier_path_proposal") or row.get("verifier_and_test_constraint_paths")),
        "has_evidence_roles": bool(row.get("candidate_options") or row.get("candidate_change_surface_paths")),
        "target_text": None,
        "train_support_only": False,
        "strict_eval_eligible": bool(row.get("strict_eval_eligible_now") or row.get("strict_eval_eligible_current")),
        "missing_for_admission": missing,
        "selected_changed_path": row.get("selected_changed_path_proposal"),
        "selected_verifier_path": row.get("selected_verifier_path_proposal"),
        "prompt_preview": "",
    }


def lane_for_candidate(candidate: dict[str, Any]) -> str | None:
    repo = str(candidate.get("repo_family") or "").lower()
    git = str(candidate.get("git_repo_family") or "").lower()
    task = str(candidate.get("task_type") or "")
    if "openhands" in repo or "openhands" in git:
        if task != "evidence_citation":
            return "materialize_diverse_openhands_transition_roots_with_test_ids_and_fail_pass_labels"
    if "llama" in repo or "llama" in git:
        return "materialize_llama_stack_train_analogues_with_selected_tests_and_root_disjoint_options"
    if task == "evidence_citation" and (
        "mcp" in repo or "modelcontextprotocol" in repo or "sep" in repo or "server" in repo
    ):
        return "build_all_supported_evidence_item_judgment_rows_with_decisive_vs_distractor_labels"
    return None


def gate_candidate(candidate: dict[str, Any], work_item: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    gates = work_item.get("admission_gates") or {}
    if candidate.get("source") in {"stage11529_queue", "stage11530_packets"}:
        blockers.extend(candidate.get("missing_for_admission") or [])
        if blockers:
            return False, sorted(set(blockers))
    if not candidate.get("has_verifier_anchor"):
        blockers.append("missing_selected_test_or_verifier_anchor")
    if "evidence_item" in str(work_item.get("action")) or candidate.get("task_type") == "evidence_citation":
        if not candidate.get("has_evidence_roles"):
            blockers.append("missing_role_distinct_evidence_ledger")
    must_tasks = set(gates.get("must_include_task_types") or [])
    if must_tasks and candidate.get("task_type") not in must_tasks and candidate.get("task_type") != "root_packet":
        blockers.append("task_not_in_required_lane")
    # Current heldout roots are diagnostic examples, not admissible fresh train material.
    root = str(candidate.get("root_id") or "")
    if "stage11390::openhands_" in root or "stage11361::llama_stack" in root:
        blockers.append("same_or_reserved_heldout_lineage")
    return not blockers, sorted(set(blockers))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work_items = load_jsonl(STAGE11574)
    candidates: list[dict[str, Any]] = []
    for row in load_jsonl(STAGE11566):
        candidates.append(candidate_from_row(row, "stage11566_support_inventory"))
    for row in load_jsonl(STAGE11550):
        candidates.append(candidate_from_row(row, "stage11550_support_manifest"))
    for row in load_jsonl(STAGE11530):
        candidates.append(candidate_from_packet(row, "stage11530_packets"))
    for row in load_jsonl(STAGE11529):
        candidates.append(candidate_from_packet(row, "stage11529_queue"))

    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        lane = lane_for_candidate(candidate)
        if lane:
            by_lane[lane].append(candidate)

    admission_rows: list[dict[str, Any]] = []
    lane_summaries: dict[str, Any] = {}
    for work_item in work_items:
        action = str(work_item.get("action"))
        lane_candidates = by_lane.get(action, [])
        admitted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for candidate in lane_candidates:
            ok, blockers = gate_candidate(candidate, work_item)
            record = dict(candidate)
            record.update({"lane_action": action, "admitted": ok, "admission_blockers": blockers})
            admission_rows.append(record)
            (admitted if ok else rejected).append(record)
        unique_admitted_roots = sorted({str(row["root_id"]) for row in admitted})
        unique_available_roots = sorted({str(row["root_id"]) for row in lane_candidates})
        min_supply = work_item.get("minimum_next_supply") or {}
        gates = work_item.get("admission_gates") or {}
        required_train = int(gates.get("minimum_train_roots") or min_supply.get("train_roots") or 0)
        required_heldout = int(gates.get("minimum_heldout_roots") or min_supply.get("heldout_roots") or 0)
        lane_summaries[action] = {
            "available_candidates": len(lane_candidates),
            "available_unique_roots": len(unique_available_roots),
            "admitted_candidates": len(admitted),
            "admitted_unique_roots": len(unique_admitted_roots),
            "required_train_roots": required_train,
            "required_heldout_roots": required_heldout,
            "root_supply_gap_for_train": max(0, required_train - len(unique_admitted_roots)),
            "root_supply_gap_for_heldout": required_heldout,
            "admitted_repo_families": dict(Counter(str(row.get("repo_family")) for row in admitted)),
            "available_repo_families": dict(Counter(str(row.get("repo_family")) for row in lane_candidates)),
            "available_task_types": dict(Counter(str(row.get("task_type")) for row in lane_candidates)),
            "rejection_reasons": dict(Counter(reason for row in rejected for reason in row.get("admission_blockers", []))),
            "sample_admitted": [row["candidate_id"] for row in admitted[:10]],
            "sample_rejected": [
                {"candidate_id": row["candidate_id"], "blockers": row["admission_blockers"]}
                for row in rejected[:10]
            ],
        }

    admitted_total = sum(lane["admitted_unique_roots"] for lane in lane_summaries.values())
    required_total = sum(lane["required_train_roots"] for lane in lane_summaries.values())
    decision = "fresh_web_root_supply_still_insufficient_do_not_train"
    if admitted_total >= required_total and all(lane["root_supply_gap_for_train"] == 0 for lane in lane_summaries.values()):
        decision = "fresh_web_root_supply_ready_for_gold_adjudication"

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": decision,
        "metrics": {
            "candidate_records_scanned": len(candidates),
            "lane_candidate_records": sum(len(rows) for rows in by_lane.values()),
            "admitted_unique_roots_total": admitted_total,
            "required_train_roots_total": required_total,
            "fresh_train_root_gap_total": max(0, required_total - admitted_total),
        },
        "lane_summaries": lane_summaries,
        "next_required_actions": [
            "Materialize additional OpenHands-style transition roots from root-disjoint sources; current admitted supply is below the 10-root gate.",
            "Materialize Llama Stack analogue roots rather than using the sealed heldout root; current usable train supply is below gate.",
            "Build MCP/SEP evidence-item judgment rows with explicit decisive/supporting/distractor roles before another evidence-head training run.",
            "Do not run another Web training probe until at least one lane reaches its fresh-root admission gate.",
        ],
        "claim_boundary": [
            "This is an admission/materialization audit, not a model score.",
            "Existing support rows are cataloged but do not override Stage11574's fresh-root requirement.",
            "No GPU execution is performed.",
        ],
        "source_artifacts": {
            "stage11574_work_items": rel(STAGE11574),
            "stage11566_candidates": rel(STAGE11566),
            "stage11550_manifest": rel(STAGE11550),
            "stage11530_packets": rel(STAGE11530),
            "stage11529_queue": rel(STAGE11529),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "candidate_supply": rel(SUPPLY),
            "admission_results": rel(ADMISSION),
        },
    }
    write_jsonl(SUPPLY, candidates)
    write_jsonl(ADMISSION, admission_rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": summary["metrics"], "lane_summaries": lane_summaries}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
