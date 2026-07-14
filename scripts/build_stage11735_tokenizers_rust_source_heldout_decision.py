#!/usr/bin/env python3
"""Decision card after tokenizers Rust source-heldout smoke scoring."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11735
NAME = "stage11735_tokenizers_rust_source_heldout_decision"
OUT = ART / NAME
SUMMARY = OUT / "tokenizers_rust_source_heldout_decision.json"

ADMISSION = ART / "stage11733_tokenizers_rust_no_train_overlap_and_admission/tokenizers_rust_no_train_overlap_and_admission.json"
SCORE = ART / "stage11734_tokenizers_rust_source_heldout_100m_score/tokenizers_rust_source_heldout_100m_score.json"


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
    admission = load_json(ADMISSION)
    score = load_json(SCORE)
    metric = score.get("metrics") or {}
    misses = score.get("misses") or []
    miss_tasks = [row.get("task_type") for row in misses]
    gates = {
        "admitted_source_heldout_smoke": admission.get("passed") is True,
        "stage11507_full_coverage": metric.get("scored_rows") == metric.get("rows") == 4,
        "stage11507_three_of_four": metric.get("correct") == 3,
        "gemma_same_manifest_attached": False,
        "full_product_ready": False,
    }
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "rust_source_heldout_smoke_partial_pass_verifier_outcome_canary",
        "passed": True,
        "gates": gates,
        "status": {
            "compact_admission": "admitted",
            "hundred_m_source_heldout_smoke": f"{metric.get('correct')}/{metric.get('rows')}",
            "miss_tasks": miss_tasks,
            "gemma_same_manifest": "not_run_gpu2_safe_backend_required",
            "full_product": "not_ready",
        },
        "interpretation": [
            "The tokenizers Rust root is exact new-root/source-snapshot attested and leak-clean after rendering.",
            "Stage11507 solves symptom_localization, evidence_citation, and patch_impact on this smoke packet.",
            "The remaining failure is verifier_outcome: the product scorer chooses a nearby inline test instead of the selected inline test anchor.",
            "Because tokenizers has prior family usage, this is a Rust source-heldout smoke canary, not broad Rust heldout proof.",
        ],
        "next_actions": [
            "Attach executable cargo test output for the selected inline test and distractor tests.",
            "Run Gemma same-manifest only through a GPU2-safe backend.",
            "Build a non-tokenizers Rust source root when local/source supply becomes available.",
            "Treat verifier_outcome as the shared Python/Rust source-heldout weakness to target next.",
        ],
        "source_artifacts": {
            "admission": rel(ADMISSION),
            "hundred_m_score": rel(SCORE),
        },
        "claim_boundary": [
            "Current selected compact frontier remains Stage11507 plus Stage11709.",
            "Rust source-heldout compact smoke is partially solved but not a clean language win.",
            "This is bounded-choice source-heldout smoke, not full-product executable repair.",
        ],
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "status": artifact["status"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
