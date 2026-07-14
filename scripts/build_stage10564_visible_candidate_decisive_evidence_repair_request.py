#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10564
NAME = "stage10564_visible_candidate_decisive_evidence_repair_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "visible_candidate_decisive_evidence_repair_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STAGE10561 = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/visible_candidate_successor_package.json"
STAGE10562 = ROOT / "runs/local/artifacts/stage10562_visible_candidate_successor_same_manifest_comparison/visible_candidate_successor_same_manifest_comparison.json"
STAGE10563 = ROOT / "runs/local/artifacts/stage10563_visible_candidate_transition_bounded_audit/visible_candidate_transition_bounded_audit.json"
STAGE10558 = ROOT / "runs/local/artifacts/stage10558_masked_projection_successor_with_v27_preservation_canary_audit/masked_projection_successor_with_v27_preservation_canary_audit.json"


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


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    s61 = load_json(STAGE10561)
    s62 = load_json(STAGE10562)
    s63 = load_json(STAGE10563)
    s58 = load_json(STAGE10558)

    decoder_summary = (((s63.get("summary") or {}).get("decoder_first_step")) or {})
    encoder_summary = (((s63.get("summary") or {}).get("encoder_option_retrieval")) or {})
    per_subtype = s63.get("per_target_subtype") or {}
    decisive_decoder = (((per_subtype.get("decisive_evidence_top1") or {}).get("decoder_first_step")) or {})
    retrieve_decoder = (((per_subtype.get("retrieve_answer_abstain") or {}).get("decoder_first_step")) or {})
    verifier_decoder = (((per_subtype.get("verifier_outcome_masked") or {}).get("decoder_first_step")) or {})

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Defines the next clean training/eval move after stage10561/10562/10563.",
            "Preserves the rebuilt 54-row visible-candidate strict slice as eval-only while targeting the real failure mode: decisive evidence selection.",
            "Keeps anti-cheat and multilingual claim hygiene explicit.",
        ],
        "inputs": {
            "stage10561_visible_candidate_package": display(STAGE10561),
            "stage10562_greedy_comparison": display(STAGE10562),
            "stage10563_bounded_transition_audit": display(STAGE10563),
            "stage10558_canary_audit": display(STAGE10558),
        },
        "current_state": {
            "stage10561_strict_rows": ((s61.get("rows") or {}).get("strict_eval")),
            "stage10562_hundred_m_greedy_exact": ((((s62.get("hundred_m") or {}).get("overall")) or {}).get("exact_accuracy")),
            "stage10562_gemma_greedy_exact": ((((s62.get("gemma12b") or {}).get("overall")) or {}).get("exact_accuracy")),
            "stage10563_decoder_first_step_accuracy": decoder_summary.get("accuracy"),
            "stage10563_encoder_option_retrieval_accuracy": encoder_summary.get("accuracy"),
            "stage10563_decisive_evidence_decoder_accuracy": decisive_decoder.get("accuracy"),
            "stage10563_retrieve_decoder_accuracy": retrieve_decoder.get("accuracy"),
            "stage10563_verifier_decoder_accuracy": verifier_decoder.get("accuracy"),
            "stage10558_canary_bounded_accuracy": (((s58.get("summary") or {}).get("bounded_accuracy"))),
        },
        "truthful_read": [
            "The rebuilt visible-candidate strict slice is now structurally scoreable and no longer blocked on missing option contracts.",
            "The stage10556 runtime does not transfer cleanly under greedy generation to the new contract, but decoder_first_step bounded scoring retains substantial competence.",
            "Most of that retained competence comes from verifier_outcome_masked and the constant retrieve_answer_abstain slice; decisive_evidence_top1 is the dominant unresolved bottleneck.",
            "Therefore the next training move should target decisive evidence selection specifically, not another broad preservation sweep.",
        ],
        "blocking_risks": [
            "retrieve_answer_abstain is still constant-A on the 54-row strict slice and should not be used as headline accuracy evidence.",
            "Using the stage10561 strict rows directly for training would contaminate the only valid rebuilt successor slice.",
            "The current multilingual win claim remains anchored in the repaired v2.7 canary, not in the rebuilt long-context successor surface.",
        ],
        "required_next_stage": {
            "recommended_stage_name": "stage10565_visible_candidate_decisive_evidence_support_package",
            "purpose": "Build fresh train-support-only multilingual visible-candidate decisive-evidence rows from disjoint roots that mimic the stage10561 contract without reusing its strict rows.",
            "must_include": [
                "python, rust, c_cpp, and web_js_ts_html support rows",
                "same visible-ledger contract as stage10561 decisive_evidence_top1",
                "hard negatives where changed_file, verification_target, and key_symbol compete closely",
                "explicit root-level split isolation and source-lineage metadata",
                "prompt-target leak audit and option-label permutation audit",
                "repo-family caps so Python does not dominate the repair set",
            ],
            "must_exclude": [
                "any stage10561 strict_eval rows or their direct permutations",
                "constant retrieve_answer_abstain rows counted toward promotion headline",
                "same-root siblings from the strict successor slice",
            ],
        },
        "promotion_gate_after_repair": [
            "No regression on stage10558 repaired v2.7 canary bounded accuracy.",
            "Improvement over stage10563 decoder_first_step decisive_evidence_top1 accuracy of 2/18 on the rebuilt stage10561 strict slice.",
            "Improvement over stage10562 greedy exact generation on the rebuilt 54-row strict slice, or explicit productization of bounded decoder_first_step scoring as the official interface.",
            "Leak audit clean on the new support package and the rebuilt strict slice.",
            "Gemma comparison reported with the same visible-choice prompt contract on the same rebuilt strict rows.",
        ],
        "longer_horizon_scale_note": [
            "Use stage10516-style root/state compilation to grow fresh support by roots, not permutations.",
            "Scale decisive-evidence support with quality ratchets: verifier-backed roots, repo caps, lineage isolation, and anti-cheat audits before row admission.",
            "Keep the 24-row repaired v2.7 canary and the 54-row rebuilt visible-candidate slice as frozen regression/eval artifacts while new roots are added elsewhere.",
        ],
        "outputs": {
            "request_json": display(OUT_JSON),
        },
    }
    write_json(OUT_JSON, payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload["current_state"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
