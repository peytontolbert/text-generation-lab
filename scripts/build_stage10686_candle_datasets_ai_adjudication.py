#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10686
NAME = "stage10686_candle_datasets_ai_adjudication"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "candle_datasets_ai_adjudication.json"
PACKETS_DIR = OUT_DIR / "review_packets"

INPUT_DIR = ARTIFACTS / "stage10685_candle_datasets_source_verifier_packet" / "review_packets" / "candle__candle-datasets"


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

    target_path = "candle-datasets/src/nlp/tinystories.rs"

    packet["claim_boundary"]["gold_answers_fully_adjudicated"] = True
    packet["claim_boundary"]["preview_only"] = False
    packet["claim_boundary"]["supports_training_or_scoring_now"] = True
    packet["discovery_metadata"]["train_support_only_admitted"] = True
    packet["discovery_metadata"]["source_derived_verifier_constraint"] = True

    for row in packet.get("perspective_rows") or []:
        row["eligible_for_training_or_scoring_now"] = True
        row["gold_answer_status"] = "completed_ai_maintainer_adjudication"
        row["prompt_contract"]["selected_tests"] = []

    rationale = (
        "Pass for train-support use. The packet now exposes a real source-derived runtime contract in tinystories.rs: the loader requires at least two .bin files and otherwise bails. That makes tinystories.rs a justified maintainer target over the more generic batcher, lib, and vision surfaces. Keep it out of headline same-surface comparison because the verifier evidence is source-derived rather than an independent test file."
    )
    anti_cheat.update(
        {
            "admissible_for_same_surface_comparison": False,
            "decision_rationale": rationale,
            "passed": True,
            "reviewer_id": "codex-gpt5-ai-review",
            "reviewer_notes": rationale,
            "status": "completed",
            "train_support_only": True,
        }
    )
    anti_cheat["challenge_families"]["placeholder_evidence_leakage"] = False
    anti_cheat["challenge_families"]["candidate_path_or_order_bias"] = False
    anti_cheat["challenge_families"]["hidden_reference_or_metadata_leakage"] = False

    visible_keys = [
        "candidate_change_surface",
        "nearby_definition_or_usage_context",
        "symptom_or_call_path_analogue",
        "verifier_and_test_constraint",
    ]
    candidate_paths = packet["candidate_paths"]
    gold_rows = [
        {
            "abstention_option_required": False,
            "candidate_paths": candidate_paths,
            "gold_answer_kind": "candidate_path",
            "gold_answer_value": target_path,
            "perspective": "symptom_localization",
            "reviewer_rationale": "The visible source path and runtime contract both point to the tinystories dataset loader rather than the generic batcher or vision helpers.",
            "selected_tests": [],
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": candidate_paths,
            "gold_answer_kind": "visible_evidence_key",
            "gold_answer_value": "verifier_and_test_constraint",
            "perspective": "evidence_citation",
            "reviewer_rationale": "The strongest visible support is the source-derived runtime contract that explicitly bails when fewer than two .bin files are present.",
            "selected_tests": [],
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": candidate_paths,
            "gold_answer_kind": "freeform_explanation",
            "gold_answer_value": "The batcher and vision files are plausible dataset-adjacent surfaces, but they do not contain the visible file-count guard or dataset-loader behavior. The tinystories loader is the strongest behavior owner.",
            "perspective": "alternative_hypothesis_elimination",
            "reviewer_rationale": "The alternative candidates are broader infrastructure or different dataset families, while the visible runtime contract belongs specifically to tinystories.rs.",
            "selected_tests": [],
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": candidate_paths,
            "gold_answer_kind": "candidate_path",
            "gold_answer_value": target_path,
            "perspective": "patch_impact",
            "reviewer_rationale": "Changing tinystories.rs most directly changes dataset-loading behavior for the visible insufficient-bin-file contract.",
            "selected_tests": [],
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": True,
            "candidate_paths": candidate_paths,
            "gold_answer_kind": "abstain",
            "gold_answer_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "perspective": "verifier_outcome",
            "reviewer_rationale": "The packet exposes a source-derived runtime contract but not an independent selected test or full observed run outcome, so abstention is the honest verifier answer.",
            "selected_tests": [],
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": candidate_paths,
            "gold_answer_kind": "candidate_path",
            "gold_answer_value": target_path,
            "perspective": "minimal_fix_selection",
            "reviewer_rationale": "The smallest maintainable intervention is to change the dataset loader that owns the insufficient-bin-files guard, not the shared batcher or unrelated vision loaders.",
            "selected_tests": [],
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": candidate_paths,
            "gold_answer_kind": "freeform_risk",
            "gold_answer_value": "Changes in candle-datasets/src/nlp/tinystories.rs could regress dataset discovery, mmap loading, token stream iteration, and train-versus-valid token handling for TinyStories consumers.",
            "perspective": "regression_risk",
            "reviewer_rationale": "The loader controls file discovery, memory mapping, and iterator setup, so regressions could affect multiple downstream dataset-consuming paths.",
            "selected_tests": [],
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": True,
            "candidate_paths": candidate_paths,
            "gold_answer_kind": "abstain",
            "gold_answer_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "perspective": "abstention_insufficient_evidence",
            "reviewer_rationale": "The packet is sufficient for train-support localization and evidence practice, but it does not expose enough independent execution evidence to justify a stronger fully verified maintainer claim.",
            "selected_tests": [],
            "visible_evidence_keys": visible_keys,
        },
    ]

    gold.update(
        {
            "bundle_gold_ready_for_eval": True,
            "decision_rationale": "AI maintainer gold answers recorded for train-support use on a fresh candle-datasets Rust root with a source-derived verifier constraint.",
            "perspective_gold_answers": gold_rows,
            "reviewer_guidance": [
                "This packet is admitted for train-support use only.",
                "Do not use this source-derived verifier packet as headline same-surface Gemma evidence.",
            ],
            "reviewer_id": "codex-gpt5-ai-review",
            "status": "completed",
            "train_support_only": True,
        }
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
        "decision": "candle_datasets_packet_ai_adjudicated_for_train_support_only",
        "bundle_id": packet["bundle_id"],
        "target_path": target_path,
        "train_support_only": True,
        "admissible_for_same_surface_comparison": False,
        "written_paths": {
            "preview_bundle": rel(preview_path),
            "anti_cheat_review_card": rel(anti_cheat_path),
            "perspective_gold_adjudication": rel(gold_path),
        },
        "claim_boundary": [
            "This stage admits one second fresh Rust root for train-support use only.",
            "The verifier evidence is source-derived from tinystories.rs rather than a separate test file.",
            "This improves Rust support breadth but does not upgrade the strict comparison claim by itself.",
        ],
        "next_best_steps": [
            "Compile the newly admitted candle-datasets packet into the reviewed v2.7 Rust support inventory.",
            "Run the next support-only probe from the preserved 22/24 runtime with both Linux and candle-datasets Rust support roots present.",
            "Continue hunting a truly independent test-anchored Rust root for stronger future comparison claims.",
        ],
    }
    write_json(SUMMARY_JSON, payload)
    print(SUMMARY_JSON)


if __name__ == "__main__":
    main()
