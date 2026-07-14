#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11600
NAME = "stage11600_web_no_abstain_geometry_probe_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_no_abstain_geometry_probe_decision.json"
POSTRUN = SUMMARIES / "stage11599_web_no_abstain_geometry_postrun_audit.json"
REQUEST = SUMMARIES / "stage11598_web_no_abstain_geometry_probe_request.json"
BASE_AUDIT = SUMMARIES / "stage11597_web_answerable_no_abstain_geometry_audit.json"
LOSS = ART / "stage11598_web_no_abstain_geometry_probe/bounded_decoder_probe/loss_by_step.jsonl"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
REJECTED_RUNTIME = ART / "stage11598_web_no_abstain_geometry_probe/runtime_model/runtime_model_bundle.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    postrun = load_json(POSTRUN)
    request = load_json(REQUEST)
    base = load_json(BASE_AUDIT)
    losses = load_jsonl(LOSS)
    contrast_applicable = sum(int(((row.get("bounded_choice_contrast_card") or {}).get("applicable_rows") or 0)) for row in losses)
    contrast_satisfied = sum(int(((row.get("bounded_choice_contrast_card") or {}).get("margin_satisfied_rows") or 0)) for row in losses)
    results = postrun.get("results") or {}
    compact = {name: {"correct": card.get("correct"), "rows": card.get("rows"), "accuracy": card.get("accuracy")} for name, card in results.items()}
    base_results = base.get("results") or {}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11598_keep_stage11507_selected_frontier",
        "selected_frontier_runtime": rel(SELECTED_RUNTIME),
        "rejected_runtime": rel(REJECTED_RUNTIME),
        "rejected_runtime_weights_sha256": load_json(REJECTED_RUNTIME).get("weights_sha256") if REJECTED_RUNTIME.exists() else None,
        "objective_settings": request.get("objective_settings"),
        "baseline_no_abstain_results": base_results,
        "postrun_compact_results": compact,
        "postrun_gates": postrun.get("gates"),
        "contrast_training_telemetry": {
            "loss_steps": len(losses),
            "contrast_applicable_rows_seen": contrast_applicable,
            "contrast_margin_satisfied_rows_seen": contrast_satisfied,
            "contrast_margin_satisfied_rate": (contrast_satisfied / contrast_applicable) if contrast_applicable else None,
        },
        "why_rejected": [
            "Stage11598 preserved all selected frontier canary/residual gates but did not improve Web heldout above 35/66.",
            "No-abstain successor strict remained 2/36, matching the Stage11597 pre-training scorer audit.",
            "This geometry avoids catastrophic interference but does not teach the current selected scorer the Web A/B task boundary.",
        ],
        "next_recommended_work": [
            "Do not run more shared retrieval CE/contrast probes on these Web rows.",
            "The next useful model change is a task-specific Web candidate scorer head or listwise same-root objective that consumes semantic_role/task_type metadata explicitly.",
            "Alternatively, build true fail-to-pass Web verifier roots; current PASS_TO_PASS rows only teach selected-test relevance.",
            "Stage11507 remains the selected frontier until a run beats Web heldout 42/66 while preserving canary/residual gates.",
        ],
        "source_artifacts": {"request": rel(REQUEST), "postrun": rel(POSTRUN), "base_audit": rel(BASE_AUDIT), "loss_by_step": rel(LOSS)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "postrun_compact_results": compact,
        "contrast_training_telemetry": summary["contrast_training_telemetry"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
