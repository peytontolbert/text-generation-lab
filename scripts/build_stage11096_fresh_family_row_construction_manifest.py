#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11096
NAME = "stage11096_fresh_family_row_construction_manifest"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_row_construction_manifest.json"
WORK_ITEMS_JSONL = OUT_DIR / "fresh_family_row_construction_work_items.jsonl"

FAMILY_CARDS = ARTIFACTS / "stage11094_fresh_family_materialization_packet" / "fresh_family_cards.jsonl"
ROOT_CARDS = ARTIFACTS / "stage11094_fresh_family_materialization_packet" / "fresh_family_root_cards.jsonl"
PACKET_ROWS = ARTIFACTS / "stage11094_fresh_family_materialization_packet" / "fresh_family_packet_rows.jsonl"


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


def make_evidence_item(root_card: dict[str, Any], family_card: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {
        "priority": ordinal,
        "workstream": "explicit_ledger_evidence_row_construction",
        "root_id": root_card.get("root_id"),
        "repo_id": root_card.get("repo_id"),
        "repo_family": root_card.get("repo_family"),
        "language_family": root_card.get("language_family"),
        "snapshot_id": root_card.get("snapshot_id"),
        "verifier_id": root_card.get("verifier_id"),
        "query_text": root_card.get("query_text"),
        "verification_targets": list(root_card.get("verification_targets") or []),
        "visible_evidence_ids": list(root_card.get("visible_evidence_ids") or []),
        "expected_changed_files": list(root_card.get("expected_changed_files") or []),
        "key_symbols": list(root_card.get("key_symbols") or []),
        "family_contract": list(family_card.get("family_contract") or []),
        "construction_goal": "Build fresh decisive-evidence rows with an explicit visible ledger and real verifier/test-constraint competition.",
        "required_outputs": [
            "At least one verifier_and_test_constraint-positive evidence_citation row.",
            "At least one candidate_change_surface-positive counterexample from the same family when source permits.",
            "Opaque options with visible evidence ledger entries and recorded option shuffle metadata.",
        ],
        "anti_cheat_requirements": [
            "No raw gold path string before options.",
            "Candidate roles must be human-judgeable from visible evidence alone.",
            "Do not alias the same visible span under multiple semantic roles unless the row is explicitly abstention-labeled.",
            "Keep sibling roots out of promotable strict eval until split assignment is frozen.",
        ],
        "admission_checks": [
            "prompt_target_leak_rows == 0",
            "deterministic_or_recorded_option_shuffle == true",
            "selected_test_or_verifier_ledger_visible == true",
            "candidate_change_surface_plausible_distractor == true",
        ],
    }


def make_verifier_item(root_card: dict[str, Any], family_card: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {
        "priority": ordinal,
        "workstream": "verifier_transition_row_construction",
        "root_id": root_card.get("root_id"),
        "repo_id": root_card.get("repo_id"),
        "repo_family": root_card.get("repo_family"),
        "language_family": root_card.get("language_family"),
        "snapshot_id": root_card.get("snapshot_id"),
        "verifier_id": root_card.get("verifier_id"),
        "query_text": root_card.get("query_text"),
        "verification_targets": list(root_card.get("verification_targets") or []),
        "visible_evidence_ids": list(root_card.get("visible_evidence_ids") or []),
        "expected_changed_files": list(root_card.get("expected_changed_files") or []),
        "key_symbols": list(root_card.get("key_symbols") or []),
        "family_contract": list(family_card.get("family_contract") or []),
        "construction_goal": "Build opaque verifier-transition rows where similar tests compete and only the real exercised target wins.",
        "required_outputs": [
            "At least one verifier_outcome row with 2+ plausible test candidates.",
            "Options encode test identity plus transition semantics, not raw filenames alone.",
            "Changed-path evidence and verifier/test ledger both visible before the decision.",
        ],
        "anti_cheat_requirements": [
            "No singleton verifier options.",
            "No direct gold test path exposure before the option list.",
            "Transition must be inferable from visible evidence rather than filename similarity.",
        ],
        "admission_checks": [
            "prompt_target_leak_rows == 0",
            "singleton_verifier_rows == 0",
            "semantic_transition_visible == true",
            "same_family_wrong_test_present == true",
        ],
    }


def main() -> None:
    family_cards = {
        str(row.get("repo_family") or ""): row
        for row in load_jsonl(FAMILY_CARDS)
    }
    root_cards = [row for row in load_jsonl(ROOT_CARDS) if bool(row.get("compiled_state_present"))]
    packet_rows = load_jsonl(PACKET_ROWS)

    scoreable_subtypes_by_root: dict[str, set[str]] = {}
    blocked_subtypes_by_root: dict[str, set[str]] = {}
    for row in packet_rows:
        root_id = str(row.get("root_id") or "")
        subtype = str(row.get("target_subtype") or "")
        if bool((row.get("scoreability") or {}).get("scoreable_now")):
            scoreable_subtypes_by_root.setdefault(root_id, set()).add(subtype)
        else:
            blocked_subtypes_by_root.setdefault(root_id, set()).add(subtype)

    work_items: list[dict[str, Any]] = []
    priority = 1
    for root_card in sorted(root_cards, key=lambda row: int(row.get("priority") or 999)):
        repo_family = str(root_card.get("repo_family") or "")
        family_card = family_cards[repo_family]
        root_id = str(root_card.get("root_id") or "")
        blocked_subtypes = blocked_subtypes_by_root.get(root_id, set())
        scoreable_subtypes = scoreable_subtypes_by_root.get(root_id, set())

        if "decisive_evidence" in blocked_subtypes:
            work_items.append(make_evidence_item(root_card, family_card, priority))
            priority += 1
        if "verifier_outcome" in scoreable_subtypes:
            work_items.append(make_verifier_item(root_card, family_card, priority))
            priority += 1

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(work_items),
        "decision": "fresh_family_row_construction_work_items_prepared",
        "claim_scope": [
            "Convert the stage11094 fresh-family packet into explicit row-construction work items.",
            "Separate evidence-ledger and verifier-transition construction so the next build attacks both geometry problems directly.",
        ],
        "source_artifacts": {
            "family_cards": rel(FAMILY_CARDS),
            "root_cards": rel(ROOT_CARDS),
            "packet_rows": rel(PACKET_ROWS),
        },
        "metrics": {
            "work_item_count": len(work_items),
            "by_workstream": dict(sorted(Counter(str(row.get("workstream") or "") for row in work_items).items())),
            "by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in work_items).items())),
            "roots_covered": len({str(row.get("root_id") or "") for row in work_items}),
        },
        "headline_findings": [
            "Every fresh-family root now has an explicit row-construction task instead of remaining an implicit queue entry.",
            "The manifest splits the next work into evidence-ledger construction and verifier-transition construction, which matches the actual plateau lanes.",
            "The anti-cheat contract is attached before row creation, not left for post hoc cleanup.",
        ],
        "next_best_step": [
            "Materialize the Python and C/C++ evidence-ledger rows first from this manifest.",
            "Build verifier-transition competition rows from at least one Python and one C/C++ family before another promotion-style probe.",
            "Keep mem0 web rows segregated until selected-test/verifier anchoring is visible enough for promotable use.",
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
