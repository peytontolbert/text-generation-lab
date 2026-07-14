#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10581
NAME = "stage10581_visible_candidate_balanced_decisive_contrast_result_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "visible_candidate_balanced_decisive_contrast_result_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

S78 = ROOT / "runs/local/artifacts/stage10578_visible_candidate_balanced_decisive_contrast_support_package/visible_candidate_balanced_decisive_contrast_support_package.json"
S80 = ROOT / "runs/local/artifacts/stage10580_visible_candidate_balanced_decisive_contrast_probe/bounded_decoder_probe/execution_result.json"
S77 = ROOT / "runs/local/artifacts/stage10577_visible_candidate_mixed_preservation_result_audit/visible_candidate_mixed_preservation_result_audit.json"
S76 = ROOT / "runs/local/artifacts/stage10576_visible_candidate_successor_same_manifest_comparison/visible_candidate_successor_same_manifest_comparison.json"


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


def strict_metric(execution: dict[str, Any], field: str) -> Any:
    return ((((execution.get("bounded_choice_eval") or {}).get("strict_eval")) or {}).get(field))


def main() -> None:
    s78 = load_json(S78)
    s80 = load_json(S80)
    s77 = load_json(S77)
    s76 = load_json(S76)

    current = {
        "stage10578_support_rows": ((s78.get("rows") or {}).get("emitted_rows")),
        "stage10580_strict_bounded_accuracy": strict_metric(s80, "constrained_choice_top1_accuracy"),
        "stage10580_strict_rows_with_target_rank_1": strict_metric(s80, "rows_with_target_rank_1"),
        "stage10580_contentful_generation_rate": s80.get("contentful_generation_rate"),
        "stage10580_runtime_weights_sha256": (((s80.get("runtime_model_bundle") or {}).get("weights_sha256"))),
        "stage10580_decisive_accuracy": 2 / 18,
        "stage10580_retrieve_accuracy": 18 / 18,
        "stage10580_verifier_accuracy": 16 / 18,
    }
    baseline = {
        "stage10577_strict_bounded_accuracy": ((s77.get("current_state") or {}).get("stage10574_strict_bounded_accuracy")),
        "stage10577_canary_bounded_accuracy": ((s77.get("current_state") or {}).get("stage10575_canary_bounded_accuracy")),
        "stage10576_hundred_m_exact": ((((s76.get("hundred_m") or {}).get("overall")) or {}).get("exact_accuracy")),
        "stage10576_hundred_m_decisive_exact": ((((s76.get("hundred_m") or {}).get("by_target_subtype")) or {}).get("decisive_evidence_top1") or {}).get("exact_accuracy"),
        "stage10576_hundred_m_retrieve_exact": ((((s76.get("hundred_m") or {}).get("by_target_subtype")) or {}).get("retrieve_answer_abstain") or {}).get("exact_accuracy"),
        "stage10576_hundred_m_verifier_exact": ((((s76.get("hundred_m") or {}).get("by_target_subtype")) or {}).get("verifier_outcome_masked") or {}).get("exact_accuracy"),
    }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "inputs": {
            "stage10578_support_package": display(S78),
            "stage10580_execution_result": display(S80),
            "stage10577_result_audit": display(S77),
            "stage10576_same_manifest_comparison": display(S76),
        },
        "current_state": current,
        "baseline_state": baseline,
        "deltas": {
            "strict_bounded_delta_vs_stage10577": None if current["stage10580_strict_bounded_accuracy"] is None or baseline["stage10577_strict_bounded_accuracy"] is None else current["stage10580_strict_bounded_accuracy"] - baseline["stage10577_strict_bounded_accuracy"],
            "decisive_accuracy_delta_vs_stage10576": None if baseline["stage10576_hundred_m_decisive_exact"] is None else current["stage10580_decisive_accuracy"] - baseline["stage10576_hundred_m_decisive_exact"],
            "retrieve_accuracy_delta_vs_stage10576": None if baseline["stage10576_hundred_m_retrieve_exact"] is None else current["stage10580_retrieve_accuracy"] - baseline["stage10576_hundred_m_retrieve_exact"],
            "verifier_accuracy_delta_vs_stage10576": None if baseline["stage10576_hundred_m_verifier_exact"] is None else current["stage10580_verifier_accuracy"] - baseline["stage10576_hundred_m_verifier_exact"],
        },
        "truthful_read": [
            "The balanced decisive-contrast support package is cleaner and better balanced by language than stage10572, but the stage10580 probe did not move the rebuilt strict frontier.",
            "Stage10580 exactly matches the current rebuilt strict bounded baseline at 36/54 and leaves the subtype split unchanged: decisive 2/18, retrieve 18/18, verifier 16/18.",
            "Because the decisive-evidence weakness did not improve, stage10580 is non-promotable even though it preserved the restored runtime behavior and saved a clean new runtime bundle.",
            "The bottleneck is no longer obvious support imbalance alone. The next useful move must change the decisive-evidence interface or add fresher, more causally explicit roots rather than another permutation-heavy replay.",
        ],
        "next_actions": [
            "Do not promote stage10580 as a new frontier runtime.",
            "Keep stage10574-stage10577 as the current honest rebuilt visible-candidate package.",
            "Treat stage10578-stage10580 as evidence that balanced permutation-weighted support by itself is insufficient to lift decisive_evidence_top1.",
            "Next decisive-evidence repair should add new answerable roots or richer evidence contracts, not just more balanced support from the same train slice.",
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
