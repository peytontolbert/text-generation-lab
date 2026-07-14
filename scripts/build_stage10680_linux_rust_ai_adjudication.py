#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10680
NAME = "stage10680_linux_rust_ai_adjudication"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "linux_rust_ai_adjudication.json"
PACKETS_DIR = OUT_DIR / "review_packets"

INPUT_DIR = ARTIFACTS / "stage10679_rust_verifier_anchor_materializer" / "review_packets" / "linux__rust"


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

    target_path = "rust/kernel/acpi.rs"
    selected_test = "samples/rust/rust_driver_platform.rs"
    selected_tests = [selected_test]

    # Remove direct candidate-path leakage from non-option evidence handles while
    # preserving the real source-derived text itself.
    packet["maintainer_visible_evidence"]["symptom_or_call_path_analogue"][0]["path"] = (
        "evidence::symptom_or_call_path::linux_platform_driver_probe"
    )
    packet["maintainer_visible_evidence"]["nearby_definition_or_usage_context"][0]["path"] = (
        "evidence::nearby_definition::linux_kernel_acpi_abstraction"
    )
    packet["maintainer_visible_evidence"]["verifier_and_test_constraint"][0]["path"] = (
        "evidence::verifier_constraint::linux_acpi_qemu_dmesg"
    )

    packet["claim_boundary"]["gold_answers_fully_adjudicated"] = True
    packet["claim_boundary"]["preview_only"] = False
    packet["claim_boundary"]["supports_training_or_scoring_now"] = True
    packet["discovery_metadata"]["train_support_only_admitted"] = True
    packet["discovery_metadata"]["selected_verifier_anchor_paths"] = selected_tests
    for row in packet.get("perspective_rows") or []:
        row["eligible_for_training_or_scoring_now"] = True
        row["gold_answer_status"] = "completed_ai_maintainer_adjudication"
        row["prompt_contract"]["selected_tests"] = selected_tests

    rationale = (
        "Pass for train-support use. The visible Linux Rust evidence is now fully source-derived, the non-option evidence handles no longer copy the candidate path verbatim, and the ACPI sample plus kernel ACPI abstraction justify rust/kernel/acpi.rs over unrelated alloc, ffi, and build helpers. Keep it out of headline same-surface comparison until additional fresh Rust roots and a second independent verifier-anchored packet are available."
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

    gold_rows = [
        {
            "abstention_option_required": False,
            "candidate_paths": packet["candidate_paths"],
            "gold_answer_kind": "candidate_path",
            "gold_answer_value": target_path,
            "perspective": "symptom_localization",
            "reviewer_rationale": "The visible driver sample is explicitly an ACPI match-table and probe path, and the nearby kernel ACPI abstraction is the only candidate surface aligned with that behavior.",
            "selected_tests": selected_tests,
            "visible_evidence_keys": [
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
        },
        {
            "abstention_option_required": False,
            "candidate_paths": packet["candidate_paths"],
            "gold_answer_kind": "visible_evidence_key",
            "gold_answer_value": "symptom_or_call_path_analogue",
            "perspective": "evidence_citation",
            "reviewer_rationale": "The strongest visible support is the ACPI-oriented sample driver path itself: it imports acpi, defines an ACPI device table, and demonstrates the probe behavior that the target abstraction governs.",
            "selected_tests": selected_tests,
            "visible_evidence_keys": [
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
        },
        {
            "abstention_option_required": False,
            "candidate_paths": packet["candidate_paths"],
            "gold_answer_kind": "freeform_explanation",
            "gold_answer_value": "The alloc, ffi, bindings, and build helper files are plausible only at a generic Rust-support level. The visible evidence is specifically about ACPI device matching and probe behavior, so rust/kernel/acpi.rs is better justified than those unrelated infrastructure candidates.",
            "perspective": "alternative_hypothesis_elimination",
            "reviewer_rationale": "A maintainer can rule out the generic infrastructure files because the visible symptom and verifier context are explicitly ACPI-specific.",
            "selected_tests": selected_tests,
            "visible_evidence_keys": [
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
        },
        {
            "abstention_option_required": False,
            "candidate_paths": packet["candidate_paths"],
            "gold_answer_kind": "candidate_path",
            "gold_answer_value": target_path,
            "perspective": "patch_impact",
            "reviewer_rationale": "A change in rust/kernel/acpi.rs most directly affects ACPI driver matching and probe semantics, which is the behavior exposed by the visible driver sample and verifier path.",
            "selected_tests": selected_tests,
            "visible_evidence_keys": [
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
        },
        {
            "abstention_option_required": False,
            "candidate_paths": packet["candidate_paths"],
            "gold_answer_kind": "selected_test",
            "gold_answer_value": selected_test,
            "perspective": "verifier_outcome",
            "reviewer_rationale": "The visible verifier constraint is the ACPI/QEMU driver validation path in samples/rust/rust_driver_platform.rs, including the expected dmesg probe outcome.",
            "selected_tests": selected_tests,
            "visible_evidence_keys": [
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
        },
        {
            "abstention_option_required": False,
            "candidate_paths": packet["candidate_paths"],
            "gold_answer_kind": "candidate_path",
            "gold_answer_value": target_path,
            "perspective": "minimal_fix_selection",
            "reviewer_rationale": "The smallest justified maintainer move is to operate at the ACPI abstraction rather than broad allocator or FFI support layers, because the evidence is about ACPI matching semantics.",
            "selected_tests": selected_tests,
            "visible_evidence_keys": [
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
        },
        {
            "abstention_option_required": False,
            "candidate_paths": packet["candidate_paths"],
            "gold_answer_kind": "freeform_risk",
            "gold_answer_value": "Changes in rust/kernel/acpi.rs could regress Rust platform-driver matching, ACPI device-table lookup, and probe behavior for other drivers that depend on the same kernel ACPI abstraction.",
            "perspective": "regression_risk",
            "reviewer_rationale": "The target abstraction sits beneath driver matching and probe flow, so regressions would likely fan out across Rust ACPI consumers rather than stay local to one sample.",
            "selected_tests": selected_tests,
            "visible_evidence_keys": [
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
        },
        {
            "abstention_option_required": True,
            "candidate_paths": packet["candidate_paths"],
            "gold_answer_kind": "abstain",
            "gold_answer_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "perspective": "abstention_insufficient_evidence",
            "reviewer_rationale": "The packet is sufficient for target localization, but it does not expose a concrete failing diff or unique line-level edit, so the honesty perspective remains abstain rather than pretending a fully specified fix is visible.",
            "selected_tests": selected_tests,
            "visible_evidence_keys": [
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
        },
    ]
    gold.update(
        {
            "bundle_gold_ready_for_eval": True,
            "decision_rationale": "AI maintainer gold answers recorded for train-support use on a fresh Linux Rust ACPI root with source-derived verifier evidence.",
            "perspective_gold_answers": gold_rows,
            "reviewer_guidance": [
                "This packet is admitted for train-support use only.",
                "Do not use this single newly recovered Rust root as headline same-surface Gemma evidence until a second independent verifier-anchored Rust packet is admitted.",
            ],
            "reviewer_id": "codex-gpt5-ai-review",
            "status": "completed",
            "train_support_only": True,
        }
    )

    preview_path = PACKETS_DIR / "linux__rust" / "fresh_rust_bundle_preview.json"
    anti_cheat_path = PACKETS_DIR / "linux__rust" / "anti_cheat_review_card.json"
    gold_path = PACKETS_DIR / "linux__rust" / "perspective_gold_adjudication.json"
    write_json(preview_path, packet)
    write_json(anti_cheat_path, anti_cheat)
    write_json(gold_path, gold)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "linux_rust_packet_ai_adjudicated_for_train_support_only",
        "claim_scope": [
            "Finalize AI anti-cheat review and AI gold adjudication for the recovered Linux Rust packet.",
            "Admit the packet for train-support use while keeping it out of headline same-surface comparison claims.",
        ],
        "bundle_id": packet["bundle_id"],
        "target_path": target_path,
        "selected_test": selected_test,
        "train_support_only": True,
        "admissible_for_same_surface_comparison": False,
        "written_paths": {
            "preview_bundle": rel(preview_path),
            "anti_cheat_review_card": rel(anti_cheat_path),
            "perspective_gold_adjudication": rel(gold_path),
        },
        "claim_boundary": [
            "This stage admits one Linux Rust packet for train-support use only.",
            "It does not upgrade the packet into a headline same-surface Rust comparison claim.",
            "A second independent verifier-anchored Rust packet is still needed for stronger multilingual frontier claims.",
        ],
        "next_best_steps": [
            "Compile the newly admitted Linux Rust packet into the next reviewed multilingual support manifest.",
            "Recover a verifier-anchored candle-datasets or candle-transformers packet to create a second independent fresh Rust root.",
            "Keep the 22/24 repaired v2.7 frontier as the canary while testing future support-only Rust expansions.",
        ],
    }
    write_json(SUMMARY_JSON, payload)
    print(SUMMARY_JSON)


if __name__ == "__main__":
    main()
