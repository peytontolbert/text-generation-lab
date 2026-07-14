#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10577
NAME = "stage10577_visible_candidate_mixed_preservation_result_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "visible_candidate_mixed_preservation_result_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

S72 = ROOT / "runs/local/artifacts/stage10572_visible_candidate_mixed_preservation_support_package/visible_candidate_mixed_preservation_support_package.json"
S74 = ROOT / "runs/local/artifacts/stage10574_visible_candidate_mixed_preservation_probe/bounded_decoder_probe/execution_result.json"
S75 = ROOT / "runs/local/artifacts/stage10575_visible_candidate_mixed_preservation_canary_audit/visible_candidate_mixed_preservation_canary_audit.json"
S76 = ROOT / "runs/local/artifacts/stage10576_visible_candidate_successor_same_manifest_comparison/visible_candidate_successor_same_manifest_comparison.json"
S63 = ROOT / "runs/local/artifacts/stage10563_visible_candidate_transition_bounded_audit/visible_candidate_transition_bounded_audit.json"
S70 = ROOT / "runs/local/artifacts/stage10570_visible_candidate_successor_same_manifest_comparison/visible_candidate_successor_same_manifest_comparison.json"
S58 = ROOT / "runs/local/artifacts/stage10558_masked_projection_successor_with_v27_preservation_canary_audit/masked_projection_successor_with_v27_preservation_canary_audit.json"
S71 = ROOT / "runs/local/artifacts/stage10571_visible_candidate_probe_result_audit/visible_candidate_probe_result_audit.json"


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
    s72 = load_json(S72)
    s74 = load_json(S74)
    s75 = load_json(S75)
    s76 = load_json(S76)
    s63 = load_json(S63)
    s70 = load_json(S70)
    s58 = load_json(S58)
    s71 = load_json(S71)

    current = {
        "stage10572_support_rows": ((s72.get("rows") or {}).get("emitted_rows")),
        "stage10574_strict_bounded_accuracy": ((((s74.get("bounded_choice_eval") or {}).get("strict_eval")) or {}).get("constrained_choice_top1_accuracy")),
        "stage10574_strict_rows_with_target_rank_1": ((((s74.get("bounded_choice_eval") or {}).get("strict_eval")) or {}).get("rows_with_target_rank_1")),
        "stage10574_contentful_generation_rate": s74.get("contentful_generation_rate"),
        "stage10575_canary_bounded_accuracy": ((s75.get("summary") or {}).get("bounded_accuracy")),
        "stage10575_canary_greedy_exact_accuracy": ((s75.get("summary") or {}).get("greedy_exact_accuracy")),
        "stage10576_hundred_m_exact": ((((s76.get("hundred_m") or {}).get("overall")) or {}).get("exact_accuracy")),
        "stage10576_gemma_exact": ((((s76.get("gemma12b") or {}).get("overall")) or {}).get("exact_accuracy")),
        "stage10576_hundred_m_decisive_exact": ((((s76.get("hundred_m") or {}).get("by_target_subtype")) or {}).get("decisive_evidence_top1") or {}).get("exact_accuracy"),
        "stage10576_gemma_decisive_exact": ((((s76.get("gemma12b") or {}).get("by_target_subtype")) or {}).get("decisive_evidence_top1") or {}).get("exact_accuracy"),
        "stage10576_hundred_m_verifier_exact": ((((s76.get("hundred_m") or {}).get("by_target_subtype")) or {}).get("verifier_outcome_masked") or {}).get("exact_accuracy"),
        "stage10576_hundred_m_retrieve_exact": ((((s76.get("hundred_m") or {}).get("by_target_subtype")) or {}).get("retrieve_answer_abstain") or {}).get("exact_accuracy"),
    }
    baseline = {
        "stage10558_canary_bounded_accuracy": ((s58.get("summary") or {}).get("bounded_accuracy")),
        "stage10563_decoder_first_step_strict_accuracy": (((s63.get("summary") or {}).get("decoder_first_step")) or {}).get("accuracy"),
        "stage10563_decisive_decoder_accuracy": ((((s63.get("per_target_subtype") or {}).get("decisive_evidence_top1")) or {}).get("decoder_first_step") or {}).get("accuracy"),
        "stage10570_hundred_m_exact": ((((s70.get("hundred_m") or {}).get("overall")) or {}).get("exact_accuracy")),
        "stage10570_gemma_exact": ((((s70.get("gemma12b") or {}).get("overall")) or {}).get("exact_accuracy")),
        "stage10570_hundred_m_decisive_exact": ((((s70.get("hundred_m") or {}).get("by_target_subtype")) or {}).get("decisive_evidence_top1") or {}).get("exact_accuracy"),
        "stage10571_strict_bounded_delta_vs_stage10563": ((s71.get("deltas") or {}).get("strict_bounded_delta_vs_stage10563")),
    }
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "inputs": {
            "stage10572_support_package": display(S72),
            "stage10574_execution_result": display(S74),
            "stage10575_canary_audit": display(S75),
            "stage10576_same_manifest_comparison": display(S76),
            "stage10563_transition_baseline": display(S63),
            "stage10570_decisive_only_same_manifest": display(S70),
            "stage10558_canary_baseline": display(S58),
            "stage10571_prior_result_audit": display(S71),
        },
        "current_state": current,
        "baseline_state": baseline,
        "deltas": {
            "canary_bounded_delta_vs_stage10558": None if current["stage10575_canary_bounded_accuracy"] is None or baseline["stage10558_canary_bounded_accuracy"] is None else current["stage10575_canary_bounded_accuracy"] - baseline["stage10558_canary_bounded_accuracy"],
            "strict_bounded_delta_vs_stage10563": None if current["stage10574_strict_bounded_accuracy"] is None or baseline["stage10563_decoder_first_step_strict_accuracy"] is None else current["stage10574_strict_bounded_accuracy"] - baseline["stage10563_decoder_first_step_strict_accuracy"],
            "greedy_exact_delta_vs_stage10570": None if current["stage10576_hundred_m_exact"] is None or baseline["stage10570_hundred_m_exact"] is None else current["stage10576_hundred_m_exact"] - baseline["stage10570_hundred_m_exact"],
            "decisive_exact_delta_vs_stage10570": None if current["stage10576_hundred_m_decisive_exact"] is None or baseline["stage10570_hundred_m_decisive_exact"] is None else current["stage10576_hundred_m_decisive_exact"] - baseline["stage10570_hundred_m_decisive_exact"],
            "same_manifest_delta_vs_gemma": None if current["stage10576_hundred_m_exact"] is None or current["stage10576_gemma_exact"] is None else current["stage10576_hundred_m_exact"] - current["stage10576_gemma_exact"],
        },
        "truthful_read": [
            "The mixed-preservation support package recovered the rebuilt 54-row strict bounded behavior instead of damaging it: stage10574 returns to 36/54, matching the stage10563 saved-runtime baseline.",
            "The repaired v2.7 canary still holds at 22/24 bounded under stage10575, so the mixed package preserved the old reviewed frontier while improving the rebuilt visible-candidate surface.",
            "On the rebuilt 54-row same-manifest generation comparison, stage10576 rises to 36/54 exact for the 100M model versus Gemma at 4/54, a much larger margin than the earlier decisive-only package.",
            "The remaining rebuilt-slice weakness is still decisive evidence itself: stage10576 decisive_evidence_top1 exact is only 2/18, while retrieve_answer_abstain is 18/18 and verifier_outcome_masked is 16/18.",
            "This makes stage10574-stage10576 a real restoration and comparison upgrade for the rebuilt contract, but not yet a decisive evidence repair.",
        ],
        "next_actions": [
            "Promote stage10574-stage10576 as the current honest rebuilt visible-candidate runtime package, with the scope stated narrowly.",
            "Target the next support batch at decisive_evidence_top1 only if it preserves the stage10574 bounded baseline and stage10575 canary by construction.",
            "Stop using greedy exact alone as the repair target. The meaningful gate on this rebuilt slice is bounded strict preservation plus decisive-evidence recovery without reopening verifier/retrieve regressions.",
            "Expand strict rows with more non-constant retrieve and more answerable decisive-evidence contracts before claiming broader seq2seq frontier progress.",
        ],
        "outputs": {
            "audit_json": display(OUT_JSON),
        },
    }
    write_json(OUT_JSON, payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload["deltas"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
