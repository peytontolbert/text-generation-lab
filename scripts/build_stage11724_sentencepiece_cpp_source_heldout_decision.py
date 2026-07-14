#!/usr/bin/env python3
"""Decision card after sentencepiece C++ source-heldout smoke scoring."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11724
NAME = "stage11724_sentencepiece_cpp_source_heldout_decision"
OUT = ART / NAME
SUMMARY = OUT / "sentencepiece_cpp_source_heldout_decision.json"

PREFLIGHT = ART / "stage11721_sentencepiece_cpp_source_heldout_smoke_preflight/sentencepiece_cpp_source_heldout_smoke_preflight.json"
SCORE = ART / "stage11722_sentencepiece_cpp_source_heldout_100m_score/sentencepiece_cpp_source_heldout_100m_score.json"
DIAG = ART / "stage11723_sentencepiece_cpp_source_heldout_scorer_diagnostic/sentencepiece_cpp_source_heldout_scorer_diagnostic.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    preflight = load_json(PREFLIGHT)
    score = load_json(SCORE)
    diag = load_json(DIAG)
    metric = score.get("metrics") or {}
    diag_metrics = diag.get("metrics_by_scorer") or {}
    all_scorers_abstain = all(
        ((entry.get("predicted_labels") or {}).get("E") == entry.get("scored_rows"))
        for entry in diag_metrics.values()
        if entry.get("scored_rows")
    )
    gates = {
        "compact_smoke_admitted": preflight.get("compact_source_heldout_smoke_ready") is True,
        "stage11507_scored_full_coverage": metric.get("scored_rows") == metric.get("rows") == 4,
        "stage11507_all_correct": metric.get("correct") == 4,
        "all_diagnostic_scorers_abstain": all_scorers_abstain,
        "gemma_same_manifest_attached": False,
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "admitted_source_heldout_smoke_failed_by_current_100m_preserve_as_failure_canary",
        "passed": True,
        "gates": gates,
        "status": {
            "compact_admission": "admitted",
            "hundred_m_source_heldout_smoke": f"{metric.get('correct')}/{metric.get('rows')}",
            "diagnostic_scorer_pattern": "all_tested_scorers_predict_abstain"
            if all_scorers_abstain
            else "scorer_variance",
            "gemma_same_manifest": "not_run_gpu2_safe_backend_required",
            "full_product": "not_ready",
        },
        "interpretation": [
            "The new sentencepiece root is useful because it is exact new-root/source-snapshot attested and leak-clean after rendering.",
            "It is not evidence of source-heldout 100M superiority: Stage11507 scores 0/4 and every tested scorer chooses abstain.",
            "The failure is likely a mix of true source-heldout weakness and row geometry: every row offers abstain while verifier evidence is static selected-test anchoring, not executed verifier output.",
            "Do not train on this strict smoke root unless it is explicitly demoted to support after a split/claim decision.",
        ],
        "next_actions": [
            "Materialize executable sentencepiece verifier output or rebuild the packet as explicit selected-test-anchor classification without an abstain option.",
            "Run Gemma same-manifest only through a GPU2-safe backend; avoid using the existing GPU1 Ollama service for this run.",
            "Create at least one Python and one Rust source-heldout smoke root before any multilingual source-heldout claim.",
            "Use this C++ root as a source-heldout failure canary for future model/scorer improvements.",
        ],
        "source_artifacts": {
            "preflight": rel(PREFLIGHT),
            "hundred_m_score": rel(SCORE),
            "scorer_diagnostic": rel(DIAG),
        },
        "claim_boundary": [
            "Current selected compact product policy remains Stage11507 plus Stage11709.",
            "Stage11724 does not change the selected frontier.",
            "This stage narrows the source-heldout status: C++ smoke admission exists, but current 100M does not solve it.",
        ],
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "status": artifact["status"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
