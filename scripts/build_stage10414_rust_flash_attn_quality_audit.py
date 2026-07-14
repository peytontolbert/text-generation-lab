#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/data/agentkernel-seq2seq-text-lab")
OUT_DIR = ROOT / "runs/local/artifacts/stage10414_rust_flash_attn_quality_audit"

FLASH = ROOT / "runs/local/artifacts/stage10413_fresh_rust_flash_attn_preview/fresh_rust_flash_attn_preview_bundle.json"
RUST_REVIEW = ROOT / "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets"
RUST_ATLAS = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def bundle_snapshot(name: str, bundle: dict) -> dict:
    evidence = bundle.get("maintainer_visible_evidence", {})
    return {
        "name": name,
        "bundle_id": bundle.get("bundle_id"),
        "candidate_paths_count": len(bundle.get("candidate_paths") or []),
        "selected_tests_count": len(bundle.get("selected_tests") or []),
        "visible_evidence_keys": sorted(k for k, v in evidence.items() if v),
        "has_verifier_and_test_constraint": bool(evidence.get("verifier_and_test_constraint")),
        "has_build_candidate": any(Path(p).name == "build.rs" for p in (bundle.get("candidate_paths") or [])),
        "has_abstention_perspective": any(
            row.get("perspective") == "abstention_insufficient_evidence"
            for row in (bundle.get("perspective_rows") or [])
        ),
    }


def review_verdict(packet_dir: Path) -> dict:
    rubric = load_json(packet_dir / "expert_maintainer_rubric_review.json")
    anti = load_json(packet_dir / "anti_cheat_review_card.json")
    gold = load_json(packet_dir / "perspective_gold_adjudication.json")
    return {
        "bundle_id": rubric.get("bundle_id"),
        "bundle_valid_for_eval": rubric.get("bundle_valid_for_eval"),
        "admissible_for_same_surface_comparison": anti.get("admissible_for_same_surface_comparison"),
        "gold_ready": gold.get("bundle_gold_ready_for_eval"),
        "decision_rationale": rubric.get("decision_rationale"),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    flash = load_json(FLASH)
    atlas = load_json(RUST_ATLAS)

    candle_examples = review_verdict(RUST_REVIEW / "stage10126__candle__candle-examples__rust")
    candle_nn = review_verdict(RUST_REVIEW / "stage10126__candle__candle-nn__rust")
    candle_core = review_verdict(RUST_REVIEW / "stage10126__candle__candle-core__rust")
    tokenizers = review_verdict(RUST_REVIEW / "stage10126__tokenizers__tokenizers__rust")

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stage": 10414,
        "stage_name": "stage10414_rust_flash_attn_quality_audit",
        "flash_attn_snapshot": bundle_snapshot("flash_attn_preview", flash),
        "comparison_targets": {
            "candle_core_reviewed_valid": candle_core,
            "tokenizers_reviewed_valid": tokenizers,
            "candle_examples_reviewed_invalid": candle_examples,
            "candle_nn_reviewed_invalid": candle_nn,
        },
        "atlas_context": {
            "best_fresh_candidate": atlas["top_fresh_candidates"][0]["candidate_root_id"],
            "fresh_with_test_files": atlas["metrics"]["fresh_with_test_files"],
            "fresh_review_ready_count": atlas["metrics"]["fresh_review_ready_count"],
        },
        "claim_boundary": [
            "The flash-attn preview is still not admitted; this audit only shows that it is structurally stronger than the previously invalid fresh Rust bundles.",
            "Its main quality advantage is the presence of a selected test plus explicit verifier-and-build constraint evidence on top of implementation candidates.",
        ],
        "promotion_readiness_read": {
            "stronger_than_candle_examples_and_candle_nn_for_next_review": True,
            "already_equivalent_to_admitted_candle_core_or_tokenizers": False,
            "needs_review_packets_and_gold_adjudication_next": True,
        },
        "next_best_step": "Route flash-attn through the Rust review-packet/signoff path and compare its adjudicated outcome against candle-core/tokenizers before using it for multilingual scaling or training support.",
    }

    (OUT_DIR / "rust_flash_attn_quality_audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
