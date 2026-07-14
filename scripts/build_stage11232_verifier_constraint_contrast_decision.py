#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11232
NAME = "stage11232_verifier_constraint_contrast_decision"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "verifier_constraint_contrast_decision.json"
AUDIT = ARTIFACTS / "stage11231_verifier_constraint_contrast_postrun_audit/verifier_constraint_contrast_postrun_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    audit = load_json(AUDIT)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reject_verifier_constraint_contrast_branch_for_promotion",
        "source_artifacts": {"postrun_audit": rel(AUDIT)},
        "key_result": audit.get("key_metrics"),
        "gates": audit.get("gates"),
        "interpretation": [
            "The existing candidate-vs-verifier contrastive margin loss preserved the clean strict canary but did not move the residual bank.",
            "Validation improved from 20/23 to 21/23, but the promotable residual gates stayed flat: 5/10 overall and 0/3 verifier_and_test_constraint.",
            "The remaining evidence failure is not fixed by more support rows, independent binary CE, class balancing, or the existing pairwise contrast loss.",
        ],
        "recommended_next_work": [
            "Stop probing current scorer variants on this residual bank unless a new architecture or materially new root-disjoint evidence supply is introduced.",
            "Build a source-row grouped evidence scorer where all evidence candidates for one maintainer decision are scored jointly with exactly-one or set-valued targets.",
            "Add fresh root-disjoint verifier/test-constraint heldout rows, especially Rust/Web selected-test anchored roots, before the next promotion claim.",
            "Keep Stage11200/clean strict 22/22 as the canary; reject Stage11227 and Stage11230 runtimes for promotion.",
        ],
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
