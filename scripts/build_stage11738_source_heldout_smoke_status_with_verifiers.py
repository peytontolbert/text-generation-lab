#!/usr/bin/env python3
"""Update source-heldout smoke status after verifier execution attachment."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11738
NAME = "stage11738_source_heldout_smoke_status_with_verifiers"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_smoke_status_with_verifiers.json"

PREV_STATUS = ART / "stage11736_source_heldout_smoke_status/source_heldout_smoke_status.json"
VERIFIERS = ART / "stage11737_source_heldout_verifier_execution/source_heldout_verifier_execution.json"


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
    prev = load_json(PREV_STATUS)
    verifiers = load_json(VERIFIERS)
    verifier_runs = verifiers.get("verifier_runs") or {}
    language_status = prev.get("language_status") or {}
    for language, status in language_status.items():
        run = verifier_runs.get(language) or {}
        status["executable_verifier_attached"] = bool(run.get("passed"))
        status["verifier_stdout_log"] = run.get("stdout_log")
        status["verifier_stderr_log"] = run.get("stderr_log")
        status["verifier_transition"] = (verifiers.get("verifier_transitions") or {}).get(language)

    gates = dict(prev.get("gates") or {})
    gates.update(
        {
            "all_executable_verifiers_attached": all(
                bool(status.get("executable_verifier_attached")) for status in language_status.values()
            ),
            "still_all_100m_smoke_rows_correct": gates.get("all_100m_smoke_rows_correct") is True,
            "still_all_gemma_same_manifest_attached": gates.get("all_gemma_same_manifest_attached") is True,
            "still_full_product_ready": False,
        }
    )

    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "source_heldout_smoke_verifiers_attached_but_claim_not_ready",
        "passed": True,
        "gates": gates,
        "selected_frontier": prev.get("selected_frontier"),
        "language_status": language_status,
        "verifier_artifact": rel(VERIFIERS),
        "interpretation": [
            "Python, C/C++ and Rust smoke roots now have executable verifier logs attached.",
            "The verifier observations are current-state PASS results, not fail-to-pass repair episodes.",
            "This upgrades evidence quality for the smoke roots but does not change the 100M compact smoke scores.",
            "The C++ 0/4 scorer failure and Python/Rust verifier_outcome misses remain the immediate model/scorer weaknesses.",
        ],
        "next_actions": [
            "Run Gemma same-manifest on these exact smoke rows through a GPU2-safe backend.",
            "Use verifier logs to rebuild verifier_outcome candidate geometry for Python and Rust.",
            "Repair C++ sentencepiece geometry with verifier-grounded non-abstain/abstain counterfactual analogues.",
            "Add harness_run_id, tool_trace_spans, and patch_minimality_or_abstain_scores only after task-pack execution exists.",
        ],
        "claim_boundary": [
            "Supported: source-heldout smoke roots now have real verifier execution evidence.",
            "Not supported: source-heldout 100M over Gemma claim for Python/C++/Rust smoke roots.",
            "Not supported: full-product patch/verifier repair claim.",
        ],
        "source_artifacts": {
            "previous_status": rel(PREV_STATUS),
            "verifier_execution": rel(VERIFIERS),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
