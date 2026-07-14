#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11060
NAME = "stage11060_ready_lane_row_construction_manifest"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "ready_lane_row_construction_manifest.json"
WORK_ITEMS_JSONL = OUT_DIR / "row_construction_work_items.jsonl"

LANE_CARDS = ARTIFACTS / "stage11059_ready_lane_materialization_packet" / "ready_lane_cards.jsonl"
ROOT_CARDS = ARTIFACTS / "stage11059_ready_lane_materialization_packet" / "ready_root_cards.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def candidate_ref_for_lane(lane_card: dict[str, Any]) -> dict[str, Any] | None:
    refs = list(lane_card.get("candidate_refs") or [])
    return refs[0] if refs else None


def reviewed_bundle_refs_for_lane(lane_card: dict[str, Any]) -> list[dict[str, Any]]:
    return list(lane_card.get("reviewed_bundle_refs") or [])


def make_evidence_item(root_card: dict[str, Any], lane_card: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {
        "priority": ordinal,
        "workstream": "explicit_ledger_evidence_row_construction",
        "lane": root_card.get("lane"),
        "target_family": root_card.get("target_family"),
        "root_id": root_card.get("root_id"),
        "repo_family": root_card.get("repo_family"),
        "repo_id": root_card.get("repo_id"),
        "language_family": root_card.get("language_family"),
        "task_family": root_card.get("task_family"),
        "query_text": root_card.get("query_text"),
        "verification_targets": list(root_card.get("verification_targets") or []),
        "visible_evidence_ids": list(root_card.get("visible_evidence_ids") or []),
        "retrieval_event_artifact_refs": list(root_card.get("retrieval_event_artifact_refs") or []),
        "seed_verifier_id": root_card.get("verifier_id"),
        "reviewed_bundle_refs": reviewed_bundle_refs_for_lane(lane_card),
        "candidate_anchor_ref": candidate_ref_for_lane(lane_card),
        "construction_goal": "Build fresh explicit-ledger evidence_citation rows from this root with visible candidate roles and preserved verifier anchors.",
        "required_outputs": [
            "At least one fresh evidence_citation row with opaque options and visible selected-test ledger.",
            "Candidate roles must include a plausible candidate_change_surface distractor.",
            "Gold evidence must be human-judgeable from visible prompt evidence alone.",
        ],
        "anti_cheat_requirements": [
            "No target path strings exposed before the option list.",
            "Deterministic option shuffle recorded or equivalent option-order anti-cheat evidence attached.",
            "No same-root sibling admitted into strict eval while this root is used for train/support.",
            "Visible evidence spans must not alias the same file/text under two different semantic roles unless the row is explicitly abstention-labeled.",
        ],
        "eval_hacking_checks": [
            "Run prompt_target_leak audit on every emitted row.",
            "Verify candidate_change_surface does not deterministically imply the gold role.",
            "Require a visible verifier/test-constraint field when gold is verifier-driven.",
        ],
        "promotable_if": [
            "root_disjoint_from_strict_overlay",
            "prompt_target_leak_rows == 0",
            "explicit_selected_test_ledger == true",
            "human_judgeable_visible_evidence == true",
        ],
    }


def make_verifier_item(root_card: dict[str, Any], lane_card: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {
        "priority": ordinal,
        "workstream": "verifier_transition_row_construction",
        "lane": root_card.get("lane"),
        "target_family": root_card.get("target_family"),
        "root_id": root_card.get("root_id"),
        "repo_family": root_card.get("repo_family"),
        "repo_id": root_card.get("repo_id"),
        "language_family": root_card.get("language_family"),
        "task_family": root_card.get("task_family"),
        "query_text": root_card.get("query_text"),
        "verification_targets": list(root_card.get("verification_targets") or []),
        "visible_evidence_ids": list(root_card.get("visible_evidence_ids") or []),
        "seed_verifier_id": root_card.get("verifier_id"),
        "reviewed_bundle_refs": reviewed_bundle_refs_for_lane(lane_card),
        "construction_goal": "Build fresh verifier_outcome_semantic_transition rows from this root using opaque verifier IDs and explicit transition semantics.",
        "required_outputs": [
            "At least one verifier_outcome_semantic_transition row with 2+ plausible verifier targets.",
            "Options must encode test_id plus transition semantics, not raw path-only choices.",
            "The changed-path evidence and selected-test evidence must both be visible before the choice.",
        ],
        "anti_cheat_requirements": [
            "No singleton verifier option rows.",
            "Raw gold test path hidden until after opaque option mapping.",
            "Transition label must be judged from visible evidence rather than filename similarity alone.",
        ],
        "eval_hacking_checks": [
            "Audit same-test-name collisions across options.",
            "Check that candidate path priors do not trivially determine the winning verifier target.",
            "Require at least one plausible wrong verifier target from the same family.",
        ],
        "promotable_if": [
            "root_disjoint_from_strict_overlay",
            "prompt_target_leak_rows == 0",
            "singleton_verifier_rows == 0",
            "semantic_transition_visible == true",
        ],
        "candidate_anchor_ref": candidate_ref_for_lane(lane_card),
    }


def main() -> None:
    lane_cards = load_jsonl(LANE_CARDS)
    root_cards = load_jsonl(ROOT_CARDS)
    lane_by_target_family = {str(row.get("target_family") or ""): row for row in lane_cards}

    work_items: list[dict[str, Any]] = []
    priority = 1

    for root_card in root_cards:
        target_family = str(root_card.get("target_family") or "")
        lane_card = lane_by_target_family[target_family]

        if target_family in {"python_repository_library_reviewed_next", "rust_non_tokenizers_non_alias"}:
            work_items.append(make_evidence_item(root_card, lane_card, priority))
            priority += 1
            continue

        if target_family == "parametergolf_verifier_transition":
            work_items.append(make_verifier_item(root_card, lane_card, priority))
            priority += 1
            continue

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(work_items),
        "decision": "ready_lane_row_construction_work_items_prepared",
        "claim_scope": [
            "Convert the stage11059 ready-lane packet into per-root fresh row-construction work items for Python, Rust, and C/C++.",
            "Make anti-cheat and eval-hacking requirements explicit at the row-construction step instead of relying on post hoc cleanup.",
        ],
        "source_artifacts": {
            "lane_cards": rel(LANE_CARDS),
            "root_cards": rel(ROOT_CARDS),
        },
        "metrics": {
            "work_item_count": len(work_items),
            "by_workstream": dict(sorted(Counter(str(row.get("workstream") or "") for row in work_items).items())),
            "by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in work_items).items())),
            "roots_covered": len({str(row.get("root_id") or "") for row in work_items}),
        },
        "headline_findings": [
            "Every ready compiled root now has a direct row-construction task rather than remaining implicit in the packet.",
            "Python and Rust are assigned explicit-ledger evidence construction; C/C++ parametergolf is assigned verifier-transition construction.",
            "The anti-cheat contract is now attached at creation time: option-order control, no singleton verifier rows, visible verifier anchors, and prompt-target leak checks are mandatory before admission.",
        ],
        "next_best_step": [
            "Use these work items to build the fresh multilingual row package for the next v2.7 support/eval expansion.",
            "Keep code_assist and agentkernel off the promotable path until their discovery debt is cleared with more independent roots.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "work_items_jsonl": rel(WORK_ITEMS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(WORK_ITEMS_JSONL, work_items)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
