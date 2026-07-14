#!/usr/bin/env python3
"""Decision after Stage11725 no-abstain sentencepiece diagnostic."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11726
NAME = "stage11726_sentencepiece_cpp_geometry_decision"
OUT = ART / NAME
SUMMARY = OUT / "sentencepiece_cpp_geometry_decision.json"

STAGE11722 = ART / "stage11722_sentencepiece_cpp_source_heldout_100m_score/sentencepiece_cpp_source_heldout_100m_score.json"
STAGE11723 = ART / "stage11723_sentencepiece_cpp_source_heldout_scorer_diagnostic/sentencepiece_cpp_source_heldout_scorer_diagnostic.json"
STAGE11725 = ART / "stage11725_sentencepiece_cpp_no_abstain_diagnostic/sentencepiece_cpp_no_abstain_diagnostic.json"
STAGE11725_ROWS = ART / "stage11725_sentencepiece_cpp_no_abstain_diagnostic/sentencepiece_cpp_no_abstain_score_rows.jsonl"

PRODUCT_SCORER = "encoder_option_retrieval_evidence_judgment_head"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    s11722 = load_json(STAGE11722)
    s11723 = load_json(STAGE11723)
    s11725 = load_json(STAGE11725)
    rows = [row for row in load_jsonl(STAGE11725_ROWS) if row.get("scorer") == PRODUCT_SCORER]
    product_metric = (s11725.get("metrics_by_scorer") or {}).get(PRODUCT_SCORER) or {}
    before_metric = s11722.get("metrics") or {}
    all_abstain_before = s11723.get("decision") == "sentencepiece_cpp_smoke_all_scorers_fail_abstain_attractor"
    product_predicted_b = all(str(row.get("predicted_label")) == "B" for row in rows)
    correct_tasks = [row.get("task_type") for row in rows if row.get("correct") is True]
    missed_tasks = [row.get("task_type") for row in rows if row.get("correct") is False]

    gates = {
        "stage11722_full_coverage": before_metric.get("scored_rows") == before_metric.get("rows") == 4,
        "stage11722_product_zero_of_four": before_metric.get("correct") == 0,
        "stage11723_all_scorers_abstain": all_abstain_before,
        "stage11725_product_improved_over_abstain_packet": product_metric.get("correct", 0) > before_metric.get("correct", 0),
        "stage11725_product_not_sufficient": product_metric.get("correct") < 4,
        "stage11725_product_nearby_surface_attractor": product_predicted_b,
    }
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "sentencepiece_cpp_failure_is_abstain_geometry_plus_nearby_surface_attractor",
        "passed": True,
        "gates": gates,
        "diagnosis": {
            "with_abstain_stage11722": f"{before_metric.get('correct')}/{before_metric.get('rows')}",
            "no_abstain_product_scorer_stage11725": f"{product_metric.get('correct')}/{product_metric.get('rows')}",
            "no_abstain_product_predicted_label_pattern": "B_for_all_rows" if product_predicted_b else "mixed",
            "correct_tasks_under_product_scorer": correct_tasks,
            "missed_tasks_under_product_scorer": missed_tasks,
        },
        "interpretation": [
            "Stage11722 was partly dominated by abstain geometry: every scorer chose abstain when it was offered.",
            "Removing abstain is not enough for the selected product scorer: it predicts the nearby BPE trainer surface for all no-abstain rows.",
            "The current product scorer only handles the evidence-citation row because B is also the verifier/test constraint there.",
            "This is a useful C++ source-heldout failure canary and should not be promoted as a benchmark win.",
        ],
        "next_actions": [
            "Materialize executable sentencepiece verifier output so candidate_change_surface versus nearby_training_surface is grounded by actual selected-test behavior.",
            "Build a train-support-only analogue set from other C++ roots where implementation/test anchor beats nearby trainer-like surfaces.",
            "Keep the Stage11720 strict root sealed unless explicitly demoted; do not train directly on this admitted smoke row as a promotion path.",
            "Proceed to Python and Rust source-heldout smoke creation so source-heldout status is not decided by one C++ root.",
        ],
        "source_artifacts": {
            "stage11722_score": rel(STAGE11722),
            "stage11723_scorer_diagnostic": rel(STAGE11723),
            "stage11725_no_abstain_diagnostic": rel(STAGE11725),
            "stage11725_rows": rel(STAGE11725_ROWS),
        },
        "claim_boundary": [
            "Selected compact frontier remains Stage11507 plus Stage11709.",
            "Source-heldout C++ smoke now has one admitted failure canary, not a win.",
            "Full-product harness remains unproven for this root because executable verifier and patch/minimality fields are absent.",
        ],
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "diagnosis": artifact["diagnosis"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
