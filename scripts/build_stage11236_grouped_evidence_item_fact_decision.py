#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11236
NAME = "stage11236_grouped_evidence_item_fact_decision"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "grouped_evidence_item_fact_decision.json"
AUDIT = ARTIFACTS / "stage11235_grouped_evidence_item_fact_postrun_audit/grouped_evidence_item_fact_postrun_audit.json"
PACKAGE = ARTIFACTS / "stage11233_grouped_evidence_item_fact_package/grouped_evidence_item_fact_package.json"


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
    package = load_json(PACKAGE)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reject_grouped_evidence_item_fact_branch_for_promotion",
        "source_artifacts": {"postrun_audit": rel(AUDIT), "package": rel(PACKAGE)},
        "key_result": audit.get("key_metrics"),
        "gates": audit.get("gates"),
        "package_counts": package.get("counts"),
        "interpretation": [
            "Concrete evidence-item option values removed role-alias leakage but did not improve the residual bank.",
            "The clean strict canary stayed 22/22, but residual remained 5/10 and verifier_and_test_constraint remained 0/3.",
            "The grouped diagnostic slice scored only 2/8 and one residual row was blocked for missing concrete evidence facts, so the current residual supply is partly under-materialized for this geometry.",
        ],
        "recommended_next_work": [
            "Stop using the current residual bank as the main optimization target; it has exhausted several scorer/data variants.",
            "Mine fresh root-disjoint verifier/test-constraint evidence roots with complete concrete facts for every candidate option.",
            "For architecture, build a native source-row grouped evidence scorer/head trained on complete candidate sets, not rewritten aliases or independent binary rows.",
            "Keep Stage11200 as the clean strict canary runtime until a new branch improves residuals without regression.",
        ],
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
