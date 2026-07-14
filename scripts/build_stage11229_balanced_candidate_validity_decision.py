#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11229
NAME = "stage11229_balanced_candidate_validity_decision"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "balanced_candidate_validity_decision.json"
AUDIT = ARTIFACTS / "stage11228_balanced_candidate_validity_postrun_audit/balanced_candidate_validity_postrun_audit.json"


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
    key = audit.get("key_metrics") or {}
    gates = audit.get("gates") or {}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reject_balanced_candidate_validity_branch_for_promotion",
        "source_artifacts": {"postrun_audit": rel(AUDIT)},
        "key_result": key,
        "gates": gates,
        "interpretation": [
            "Class-balanced binary support fixed the prior all-negative collapse but overcorrected into all-positive collapse.",
            "The clean strict canary stayed 22/22 and residual bank stayed 5/10, so the run is safe diagnostically but not a frontier improvement.",
            "Binary evidence-validity is still a useful target, but it needs pairwise/root-level ranking or calibrated positive-vs-negative scoring, not simple binary CE over independently projected candidates.",
        ],
        "recommended_next_work": [
            "Replace independent binary rows with paired candidate sets where one source row is scored as a group and exactly one candidate must outrank hard negatives.",
            "Use positive recall, negative specificity, and source-row solved rate as gates.",
            "Keep current clean strict/residual metrics as regression gates and do not promote Stage11227 runtime.",
            "Scale only after the paired objective solves both positive and negative classes on the diagnostic slice.",
        ],
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
