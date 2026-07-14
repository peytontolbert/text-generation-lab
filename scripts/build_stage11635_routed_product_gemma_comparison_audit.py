#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11635
NAME = "stage11635_routed_product_gemma_comparison_audit"
OUT = ART / NAME
SUMMARY = OUT / "routed_product_gemma_comparison_audit.json"

ROUTED = ART / "stage11633_routed_product_scorer_audit/routed_product_scorer_audit.json"
POLICY_FREEZE = ART / "stage11634_routed_policy_freeze_and_anticheat/routed_policy_freeze_and_anticheat.json"
WEB_GEMMA = ART / "stage11549_web_root_heldout_same_manifest_gemma_comparison/web_root_heldout_same_manifest_gemma_comparison.json"
WEB_GEMMA_ROWS = ART / "stage11549_web_root_heldout_same_manifest_gemma_comparison/web_root_heldout_gemma_rows.jsonl"
WEB_ROWS = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fraction(correct: int | None, rows: int | None) -> float | None:
    if correct is None or not rows:
        return None
    return correct / rows


def main() -> None:
    routed = load_json(ROUTED)
    policy = load_json(POLICY_FREEZE)
    gemma = load_json(WEB_GEMMA)
    web_rows = load_jsonl(WEB_ROWS)
    gemma_rows = load_jsonl(WEB_GEMMA_ROWS)

    routed_web = (routed.get("routed_results") or {}).get("web_heldout") or {}
    routed_correct = routed_web.get("correct")
    routed_rows = routed_web.get("rows")
    gemma_metric = gemma.get("gemma12b") or {}
    gemma_correct = gemma_metric.get("correct")
    gemma_count = gemma_metric.get("rows")
    stage11507 = ((gemma.get("comparison") or {}).get("hundred_m_correct"), (gemma.get("comparison") or {}).get("hundred_m_rows"))

    same_row_gemma_available = (
        WEB_GEMMA.exists()
        and WEB_GEMMA_ROWS.exists()
        and len(web_rows) == len(gemma_rows) == gemma_count == routed_rows
    )
    web_comparison = {
        "rowset": "web_root_heldout_66",
        "routed_100m_correct": routed_correct,
        "routed_100m_rows": routed_rows,
        "routed_100m_accuracy": fraction(routed_correct, routed_rows),
        "stage11507_100m_correct": stage11507[0],
        "stage11507_100m_rows": stage11507[1],
        "stage11507_100m_accuracy": fraction(stage11507[0], stage11507[1]),
        "gemma12b_correct": gemma_correct,
        "gemma12b_rows": gemma_count,
        "gemma12b_accuracy": fraction(gemma_correct, gemma_count),
        "delta_routed_100m_minus_gemma": None
        if fraction(routed_correct, routed_rows) is None or fraction(gemma_correct, gemma_count) is None
        else fraction(routed_correct, routed_rows) - fraction(gemma_correct, gemma_count),
        "delta_routed_100m_minus_stage11507": None
        if fraction(routed_correct, routed_rows) is None or fraction(stage11507[0], stage11507[1]) is None
        else fraction(routed_correct, routed_rows) - fraction(stage11507[0], stage11507[1]),
    }

    protected = {
        key: value
        for key, value in (routed.get("routed_results") or {}).items()
        if key.startswith("protected_")
    }
    gates = {
        "routed_policy_frozen": policy.get("decision") == "routed_policy_frozen_anticheat_passed",
        "routing_anticheat_passed": all((policy.get("gates") or {}).values()),
        "routed_internal_gates_passed": routed.get("decision") == "routed_product_scorer_candidate_passes_internal_gates",
        "same_row_gemma_web_available": same_row_gemma_available,
        "routed_web_beats_stage11507": (routed_correct or 0) > (stage11507[0] or 0) and routed_rows == stage11507[1],
        "routed_web_beats_gemma": (routed_correct or 0) > (gemma_correct or 0) and routed_rows == gemma_count,
    }
    decision = (
        "routed_product_beats_gemma_on_web_heldout"
        if all(gates.values())
        else "routed_product_improves_web_but_does_not_beat_gemma"
        if gates["routed_policy_frozen"] and gates["same_row_gemma_web_available"] and gates["routed_web_beats_stage11507"]
        else "routed_product_comparison_incomplete_or_blocked"
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "gates": gates,
        "web_same_manifest_comparison": web_comparison,
        "protected_routed_results": protected,
        "routed_policy_route_counts": policy.get("route_counts"),
        "claim_boundary": [
            "Stage11634 is a frozen routed product-scorer policy, not a single standalone model-weight checkpoint.",
            "The routed policy improves Web heldout over Stage11507 but does not beat the existing same-manifest Gemma-12B Web result.",
            "The compact protected canary remains strong under the Stage11507 route; Web remains the active product gap.",
            "This is bounded-choice maintainer scoring, not freeform repair or executable patch synthesis.",
        ],
        "next_actions": [
            "Do not claim broad Web superiority from the routed policy.",
            "Use Stage11634 as a product harness candidate only if the comparison statement includes the Web Gemma loss.",
            "To close the Web gap, add root-heldout OpenHands/Llama-style verifier-backed roots or train a single-weight distilled Web scorer that preserves protected gates.",
            "For RL-style scaling, count complete scored agent attempts per update, not raw optimizer steps; the current Web rowsets are too small for that regime.",
        ],
        "source_artifacts": {
            "routed_audit": rel(ROUTED),
            "routed_policy_freeze": rel(POLICY_FREEZE),
            "web_rows": rel(WEB_ROWS),
            "web_gemma_summary": rel(WEB_GEMMA),
            "web_gemma_rows": rel(WEB_GEMMA_ROWS),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "gates": gates, "web_same_manifest_comparison": web_comparison}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
