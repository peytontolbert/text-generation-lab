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
STAGE = 11583
NAME = "stage11583_web_verifier_attached_probe_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_verifier_attached_probe_decision.json"
STAGE11582 = SUMMARIES / "stage11582_web_verifier_attached_postrun_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    audit = load_json(STAGE11582)
    results = audit.get("results") or {}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "do_not_promote_stage11581_runtime_or_rows",
        "selected_frontier_remains": "stage11507+encoder_option_retrieval_evidence_judgment_head",
        "negative_result": {
            "filtered_strict": {"correct": results.get("filtered_strict", {}).get("correct"), "rows": results.get("filtered_strict", {}).get("rows")},
            "old_canary_strict": {"correct": results.get("old_canary_strict", {}).get("correct"), "rows": results.get("old_canary_strict", {}).get("rows")},
            "residual_bank": {"correct": results.get("residual_bank", {}).get("correct"), "rows": results.get("residual_bank", {}).get("rows")},
            "web_heldout": {"correct": results.get("web_heldout", {}).get("correct"), "rows": results.get("web_heldout", {}).get("rows")},
            "web_successor_strict": {"correct": results.get("web_successor_strict", {}).get("correct"), "rows": results.get("web_successor_strict", {}).get("rows")},
        },
        "diagnosis": [
            "The verifier-attached row geometry shifted labels and scorer priors too aggressively.",
            "Current-state PASS_TO_PASS rows are useful verifier evidence but not safe as direct broad training targets in this format.",
            "The zero score on successor strict indicates target/interface mismatch, not a promotable Web capability gain.",
        ],
        "next_required_actions": [
            "Keep Stage11579 verifier logs as evidence inventory.",
            "Rebuild verifier-attached rows as semantic candidate scoring examples instead of raw A/B target relabeling.",
            "Add a small scorer-only diagnostic before any full-model training.",
            "Promotion remains blocked until protected strict/canary gates are preserved and Web heldout improves beyond 42/66.",
        ],
        "claim_boundary": [
            "Stage11581 is diagnostic only.",
            "No broad Web or v2.7 promotion claim should use Stage11581.",
        ],
        "source_artifacts": {"stage11582_audit": rel(STAGE11582)},
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "negative_result": summary["negative_result"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
