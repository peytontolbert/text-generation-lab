#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10685
NAME = "stage10685_candle_datasets_source_verifier_packet"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "candle_datasets_source_verifier_packet.json"
PACKETS_DIR = OUT_DIR / "review_packets"

INPUT_DIR = ARTIFACTS / "stage10679_rust_verifier_anchor_materializer" / "review_packets" / "candle__candle-datasets"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    packet = load_json(INPUT_DIR / "fresh_rust_bundle_preview.json")
    anti_cheat = load_json(INPUT_DIR / "anti_cheat_review_card.json")
    gold = load_json(INPUT_DIR / "perspective_gold_adjudication.json")

    candidate_entries = packet["maintainer_visible_evidence"]["candidate_change_surface"]
    by_path = {entry["path"]: entry for entry in candidate_entries}

    tinystories = by_path["candle-datasets/src/nlp/tinystories.rs"]
    nlp_mod = by_path["candle-datasets/src/nlp/mod.rs"]
    batcher = by_path["candle-datasets/src/batcher.rs"]

    packet["maintainer_visible_evidence"]["symptom_or_call_path_analogue"] = [
        {
            "distance_from_seed": 0,
            "path": "evidence::symptom_or_call_path::tinystories_dataset_loader",
            "retrieval_reason": "source_derived_dataset_loader_with_runtime_file_count_guard",
            "source_type": tinystories["source_type"],
            "text": tinystories["text"],
            "meta": {
                **dict(tinystories.get("meta") or {}),
                "required_to_compete_against_candidate_change_surface": True,
                "supports_dataset_loader_localization": True,
            },
        }
    ]
    packet["maintainer_visible_evidence"]["nearby_definition_or_usage_context"] = [
        {
            "distance_from_seed": 0,
            "path": "evidence::nearby_definition::tinystories_module_export",
            "retrieval_reason": "nearby_module_export_context_for_nlp_loader",
            "source_type": nlp_mod["source_type"],
            "text": nlp_mod["text"],
            "meta": {
                **dict(nlp_mod.get("meta") or {}),
                "helps_disambiguate_close_implementation_candidates": True,
            },
        }
    ]
    packet["maintainer_visible_evidence"]["verifier_and_test_constraint"] = [
        {
            "distance_from_seed": 0,
            "path": "evidence::verifier_constraint::tinystories_requires_two_bin_files",
            "retrieval_reason": "source_derived_runtime_contract_without_external_test_file",
            "source_type": tinystories["source_type"],
            "text": tinystories["text"],
            "meta": {
                **dict(tinystories.get("meta") or {}),
                "source_derived_verifier_constraint": True,
                "verifier_anchor_kind": "runtime_contract_in_source",
            },
        }
    ]

    # Remove direct path reuse from non-option evidence so the support packet does not
    # leak the target as a trivial header match.
    packet["claim_boundary"]["preview_only"] = True
    packet["claim_boundary"]["supports_training_or_scoring_now"] = False
    packet["claim_boundary"]["verifier_anchor_still_missing"] = False
    packet["claim_boundary"]["scaffold_only_until_verifier_anchor_materialized"] = False
    packet["discovery_metadata"]["selected_verifier_anchor_paths"] = []
    packet["discovery_metadata"]["source_derived_verifier_constraint"] = True
    packet["discovery_metadata"]["target_candidate_for_ai_review"] = "candle-datasets/src/nlp/tinystories.rs"

    for row in packet.get("perspective_rows") or []:
        row["prompt_contract"]["selected_tests"] = []

    anti_cheat["status"] = "pending_source_verifier_ai_review"
    anti_cheat["decision_rationale"] = (
        "Placeholder verifier evidence has been replaced with a source-derived runtime contract from tinystories.rs, but AI anti-cheat review still needs to confirm this is honest support-only evidence."
    )
    anti_cheat["required_human_action"] = (
        "Review whether the tinystories runtime contract justifies train-support use without a separate test file, and confirm that candidate_change_surface remains a plausible but weaker negative."
    )

    gold["status"] = "pending_ai_gold_completion_after_source_verifier_recovery"
    gold["decision_rationale"] = (
        "A source-derived verifier constraint is now attached from tinystories.rs, enabling AI adjudication for train-support use without inventing a separate tests directory."
    )

    out_dir = PACKETS_DIR / "candle__candle-datasets"
    preview_path = out_dir / "fresh_rust_bundle_preview.json"
    anti_cheat_path = out_dir / "anti_cheat_review_card.json"
    gold_path = out_dir / "perspective_gold_adjudication.json"
    write_json(preview_path, packet)
    write_json(anti_cheat_path, anti_cheat)
    write_json(gold_path, gold)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "candle_datasets_packet_reframed_with_source_derived_verifier_constraint",
        "claim_scope": [
            "Replace the placeholder verifier field in the candle-datasets fresh Rust packet with a real source-derived runtime contract.",
            "Prepare the packet for AI train-support adjudication without fabricating a separate tests directory.",
        ],
        "target_candidate_path": "candle-datasets/src/nlp/tinystories.rs",
        "candidate_change_surface_negative": "candle-datasets/src/batcher.rs",
        "claim_boundary": [
            "This packet remains support-only until AI anti-cheat review and AI gold adjudication complete.",
            "The verifier constraint is source-derived from runtime checks in tinystories.rs, not from a separate test file.",
            "Even if admitted, this packet should not be upgraded into same-surface comparison evidence.",
        ],
        "written_paths": {
            "preview_bundle": rel(preview_path),
            "anti_cheat_review_card": rel(anti_cheat_path),
            "perspective_gold_adjudication": rel(gold_path),
        },
        "next_best_steps": [
            "Run AI anti-cheat review on the source-derived verifier packet.",
            "If the packet is honest enough, complete AI gold adjudication for train-support use.",
            "Then compile it into the reviewed Rust support inventory as a second independent fresh Rust root.",
        ],
    }
    write_json(SUMMARY_JSON, payload)
    print(SUMMARY_JSON)


if __name__ == "__main__":
    main()
