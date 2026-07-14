#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11095
NAME = "stage11095_fresh_family_materialization_packet_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_materialization_packet_audit.json"

PACKET_JSON = ARTIFACTS / "stage11094_fresh_family_materialization_packet" / "fresh_family_materialization_packet.json"
FAMILY_CARDS = ARTIFACTS / "stage11094_fresh_family_materialization_packet" / "fresh_family_cards.jsonl"
ROOT_CARDS = ARTIFACTS / "stage11094_fresh_family_materialization_packet" / "fresh_family_root_cards.jsonl"
PACKET_ROWS = ARTIFACTS / "stage11094_fresh_family_materialization_packet" / "fresh_family_packet_rows.jsonl"

EXHAUSTED_REPO_FAMILIES = {
    "repository_library",
    "parametergolf",
    "tokenizers",
    "candle",
    "agentkernel",
    "code_assist",
    "agentkernel-seq2seq-text-lab",
}

REQUIRED_SUBTYPES = {
    "decisive_evidence",
    "retrieve_answer_abstain",
    "verifier_outcome",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    packet_summary = load_json(PACKET_JSON)
    family_cards = load_jsonl(FAMILY_CARDS)
    root_cards = load_jsonl(ROOT_CARDS)
    packet_rows = load_jsonl(PACKET_ROWS)

    exhausted_hits = sorted(
        {
            str(row.get("repo_family") or "")
            for row in root_cards
            if str(row.get("repo_family") or "") in EXHAUSTED_REPO_FAMILIES
        }
    )
    missing_compiled_state = [
        str(row.get("root_id") or "")
        for row in root_cards
        if not bool(row.get("compiled_state_present"))
    ]

    subtypes_by_root: dict[str, set[str]] = defaultdict(set)
    scoreable_by_root: dict[str, set[str]] = defaultdict(set)
    blocked_reason_counter = Counter()
    blocked_reason_by_subtype: dict[str, Counter[str]] = defaultdict(Counter)

    for row in packet_rows:
        root_id = str(row.get("root_id") or "")
        subtype = str(row.get("target_subtype") or "")
        subtypes_by_root[root_id].add(subtype)
        scoreability = dict(row.get("scoreability") or {})
        if scoreability.get("scoreable_now"):
            scoreable_by_root[root_id].add(subtype)
        else:
            reason = str(scoreability.get("reason") or "unknown")
            blocked_reason_counter[reason] += 1
            blocked_reason_by_subtype[subtype][reason] += 1

    roots_missing_required_subtypes = {
        root_id: sorted(REQUIRED_SUBTYPES - subtypes)
        for root_id, subtypes in subtypes_by_root.items()
        if not REQUIRED_SUBTYPES.issubset(subtypes)
    }
    roots_missing_scoreable_verifier = sorted(
        root_id for root_id, subtypes in scoreable_by_root.items() if "verifier_outcome" not in subtypes
    )
    roots_missing_scoreable_retrieve = sorted(
        root_id for root_id, subtypes in scoreable_by_root.items() if "retrieve_answer_abstain" not in subtypes
    )

    blocked_reasons_not_expected = sorted(
        reason
        for reason in blocked_reason_counter
        if reason not in {
            "target_evidence_ids_are_visible_but_still_opaque_handles",
            "requires_explicit_candidate_ledger_or_evidence_projection",
        }
    )

    family_root_counts = Counter(str(row.get("repo_family") or "") for row in root_cards)
    uneven_family_counts = {
        family: count
        for family, count in sorted(family_root_counts.items())
        if count != 2
    }

    passed = not (
        exhausted_hits
        or missing_compiled_state
        or roots_missing_required_subtypes
        or roots_missing_scoreable_verifier
        or roots_missing_scoreable_retrieve
        or blocked_reasons_not_expected
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "claim_scope": [
            "Audit that the fresh-family materialization packet is actually fresh, subtype-complete, and blocked only for the expected visible-ledger reasons.",
            "Confirm every queued root is ready for the next row-construction stage with scoreable verifier/retrieve targets already present.",
        ],
        "source_artifacts": {
            "packet_summary": rel(PACKET_JSON),
            "family_cards": rel(FAMILY_CARDS),
            "root_cards": rel(ROOT_CARDS),
            "packet_rows": rel(PACKET_ROWS),
        },
        "metrics": {
            "family_count": len(family_cards),
            "root_count": len(root_cards),
            "packet_row_count": len(packet_rows),
            "rows_by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in packet_rows).items())),
            "roots_by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in root_cards).items())),
            "scoreable_rows": sum(1 for row in packet_rows if bool((row.get("scoreability") or {}).get("scoreable_now"))),
            "blocked_rows": sum(1 for row in packet_rows if not bool((row.get("scoreability") or {}).get("scoreable_now"))),
            "blocked_by_reason": dict(sorted(blocked_reason_counter.items())),
            "family_root_counts": dict(sorted(family_root_counts.items())),
            "scoreable_subtype_coverage": {
                "verifier_outcome_roots": len(root_cards) - len(roots_missing_scoreable_verifier),
                "retrieve_answer_abstain_roots": len(root_cards) - len(roots_missing_scoreable_retrieve),
            },
        },
        "findings": [
            "The fresh-family packet is only useful if every queued root already carries scoreable verifier and terminal-decision targets.",
            "Blocked decisive_evidence rows are acceptable here only when the blocker is explicit visible-ledger projection, not missing root coverage or unknown subtype handling.",
            "Two roots per family is the intended starting geometry for this packet; anything else signals skew before row construction begins.",
        ],
        "blocking_issues": {
            "exhausted_family_hits": exhausted_hits,
            "missing_compiled_state": missing_compiled_state,
            "roots_missing_required_subtypes": roots_missing_required_subtypes,
            "roots_missing_scoreable_verifier": roots_missing_scoreable_verifier,
            "roots_missing_scoreable_retrieve": roots_missing_scoreable_retrieve,
            "blocked_reasons_not_expected": blocked_reasons_not_expected,
            "uneven_family_counts": uneven_family_counts,
        },
        "packet_snapshot": packet_summary.get("metrics"),
        "next_best_step": "Use the packet rows to build explicit visible-ledger bounded rows for decisive_evidence while preserving the existing scoreable verifier and terminal-decision rows.",
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
