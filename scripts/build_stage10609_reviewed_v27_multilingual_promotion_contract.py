#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10609
NAME = "stage10609_reviewed_v27_multilingual_promotion_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "reviewed_v27_multilingual_promotion_contract.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

MANIFEST_PACKAGE = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_manifest_package.json"
COMPARISON_AUDIT = ROOT / "runs/local/artifacts/stage10424_reviewed_multilingual_v27_comparison_audit/reviewed_multilingual_v27_comparison_audit.json"
EVAL_HACKING_AUDIT = ROOT / "runs/local/artifacts/stage10429_reviewed_v27_eval_hacking_audit/reviewed_v27_eval_hacking_audit.json"
MARGIN_AUDIT = ROOT / "runs/local/artifacts/stage10431_reviewed_v27_saved_runtime_margin_audit/reviewed_v27_saved_runtime_margin_audit.json"
LEAK_CLEANUP_QUEUE = ROOT / "runs/local/artifacts/stage10432_reviewed_v27_strict_leak_cleanup_queue/reviewed_v27_strict_leak_cleanup_queue.json"
LEAK_REWRITE_HELPER = ROOT / "runs/local/artifacts/stage10435_reviewed_v27_strict_leak_rewrite_helper/reviewed_v27_strict_leak_rewrite_helper.json"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"
BASELINE_EXECUTION = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/execution_result.json"
GEMMA_COMPARISON = ROOT / "runs/local/artifacts/stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison/reviewed_multilingual_v27_same_manifest_gemma_comparison.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    manifest = load_json(MANIFEST_PACKAGE)
    comparison = load_json(COMPARISON_AUDIT)
    hacking = load_json(EVAL_HACKING_AUDIT)
    margin = load_json(MARGIN_AUDIT)
    cleanup = load_json(LEAK_CLEANUP_QUEUE)
    helper = load_json(LEAK_REWRITE_HELPER)
    gate = load_json(PROMOTION_GATE)
    baseline = load_json(BASELINE_EXECUTION)
    gemma = load_json(GEMMA_COMPARISON)
    strict = ((baseline.get("bounded_choice_eval") or {}).get("strict_eval") or {})

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "inputs": {
            "manifest_package": display(MANIFEST_PACKAGE),
            "comparison_audit": display(COMPARISON_AUDIT),
            "eval_hacking_audit": display(EVAL_HACKING_AUDIT),
            "margin_audit": display(MARGIN_AUDIT),
            "leak_cleanup_queue": display(LEAK_CLEANUP_QUEUE),
            "leak_rewrite_helper": display(LEAK_REWRITE_HELPER),
            "promotion_gate": display(PROMOTION_GATE),
            "baseline_execution": display(BASELINE_EXECUTION),
            "gemma_comparison": display(GEMMA_COMPARISON),
        },
        "claim_scope": [
            "Freezes the honest standalone multilingual v2.7 promotion path for Python, Rust, C/C++, and Web on the reviewed compact bounded maintainer surface.",
            "Separates the stable repaired-overlay standalone path from the newer semantic-output diagnostic branch.",
            "Defines what future 100M-vs-Gemma standalone claims may and may not say on v2.7.",
        ],
        "current_honest_state": {
            "same_manifest_only": True,
            "source_heldout_claim_supported": False,
            "strict_rows": strict.get("rows"),
            "standalone_target100m_constrained_choice_accuracy": strict.get("constrained_choice_top1_accuracy"),
            "standalone_target100m_full_vocab_accuracy": strict.get("full_vocab_top1_accuracy"),
            "gemma_same_manifest_strict_accuracy": ((comparison.get("current_claim") or {}).get("supported") and ((hacking.get("frontier_result") or {}).get("gemma_strict_accuracy"))),
            "target100m_vs_gemma_delta": ((hacking.get("frontier_result") or {}).get("strict_delta_vs_gemma")),
            "four_language_win_supported": True,
            "remaining_known_residual_rows": ((gate.get("current_candidate_summary") or {}).get("remaining_misses")),
        },
        "promotion_surface": {
            "surface_name": "reviewed_v27_repaired_overlay_compact_bounded_choice",
            "primary_metric": "constrained_choice_top1_accuracy",
            "secondary_metrics": [
                "per_language_constrained_choice_accuracy",
                "margin_top1_minus_top2",
                "abstention_slice_accuracy",
                "verifier_anchor_slice_accuracy",
            ],
            "blocked_metrics": [
                "full_vocab_top1_accuracy as primary standalone promotion metric",
                "any semantic-output first-token metric",
            ],
        },
        "required_honesty_gates": [
            "Strict path must remain stress-excluded and same-manifest only.",
            "Source-heldout superiority must not be claimed on v2.7 until fresh heldout reviewed roots exist.",
            "Prompt-target leak rows must remain repaired or excluded; raw pre-repair strict rows are not promotable.",
            "Residual-support runs cannot upgrade the headline unless they beat 22/24, keep zero regressions, keep overlay leak hygiene clean, and show fresh disjoint-root improvement.",
            "Standalone v2.7 claims must stay separate from full-product harness claims.",
        ],
        "anti_cheat_findings": {
            "reviewed_v27_raw_strict_leak_rows": ((cleanup.get("summary") or {}).get("strict_leak_rows")),
            "strict_leak_languages": ((cleanup.get("summary") or {}).get("strict_leak_languages")),
            "rewrite_strategy": helper.get("rewrite_strategy"),
            "metadata_majority_baseline_all_rows_repo_and_task": (((hacking.get("metadata_majority_baselines") or {}).get("all_rows") or {}).get("repo_and_task") or {}).get("accuracy"),
            "metadata_majority_baseline_strict_task_type": (((hacking.get("metadata_majority_baselines") or {}).get("strict_rows") or {}).get("task_type") or {}).get("accuracy"),
            "note": "The reviewed package is strong, but metadata/evidence-signature baselines are high enough that anti-cheat audits remain first-class, especially on evidence_citation rows.",
        },
        "language_status": {
            "python": "supported same-manifest standalone win, but one known verifier residual remains in promotion gate history",
            "rust": "supported same-manifest standalone win, but tokenizers evidence_citation remains the hardest residual family and fresh non-tokenizers reviewed roots are still needed",
            "c_cpp": "supported same-manifest standalone win on the reviewed compact surface",
            "web_js_ts_html": "supported same-manifest standalone win, but pure-web verifier-anchored source supply remains a longer-term realism gap",
        },
        "next_required_work": [
            "Finish or rebuild fresh disjoint reviewed roots for the Python verifier and Rust evidence-citation residual families.",
            "Keep the semantic-output branch diagnostic until exact-sequence or semantic constrained scoring becomes the enforced headline metric there.",
            "Add fresh source-heldout reviewed roots before upgrading any v2.7 claim beyond same-manifest standalone superiority.",
        ],
        "truthful_read": [
            "The current best honest standalone multilingual v2.7 path is still the reviewed compact bounded-choice surface, not the newer semantic-output path.",
            "That path already supports a four-language same-manifest standalone win over Gemma, but it does not yet support source-heldout or full-product-harness superiority claims.",
            "This contract keeps the repo aligned: standalone multilingual wins can still be pursued honestly while the more ambitious semantic-output and harness branches mature.",
        ],
        "outputs": {
            "promotion_contract_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, payload)
    write_json(RUN_SUMMARY_JSON, payload)
    print(json.dumps({
        "stage": STAGE,
        "primary_metric": payload["promotion_surface"]["primary_metric"],
        "strict_rows": payload["current_honest_state"]["strict_rows"],
        "four_language_win_supported": payload["current_honest_state"]["four_language_win_supported"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
