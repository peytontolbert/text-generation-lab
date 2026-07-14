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
STAGE = 11627
NAME = "stage11627_web_fail_to_pass_expanded_materialization_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_expanded_materialization_decision.json"

EXECUTOR = ART / "stage11613_web_fail_to_pass_mutation_executor/web_fail_to_pass_mutation_executor.json"
ROWS = ART / "stage11614_web_mutation_fail_to_pass_rows/web_mutation_fail_to_pass_rows.json"
ANTICHEAT = ART / "stage11615_web_mutation_rows_anticheat_audit/web_mutation_rows_anticheat_audit.json"
REPAIR = ART / "stage11621_web_fail_to_pass_row_geometry_repair/web_fail_to_pass_row_geometry_repair.json"
GEOMETRY = ART / "stage11622_web_fail_to_pass_repaired_geometry_audit/web_fail_to_pass_repaired_geometry_audit.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"


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
    executor = load_json(EXECUTOR)
    rows = load_json(ROWS)
    anticheat = load_json(ANTICHEAT)
    repair = load_json(REPAIR)
    geometry = load_json(GEOMETRY)
    compact = geometry["compact"]
    gates = {
        "admitted_roots_at_least_8": int(executor.get("total_admitted_roots") or 0) >= 8,
        "has_llama_admitted_roots": any("llama_stack" in str(root) for root in executor.get("admitted_root_ids", [])),
        "anti_cheat_admitted_all_rows": anticheat.get("admitted_rows") == rows.get("train_rows") and anticheat.get("rejected_rows") == 0,
        "repair_admitted": repair.get("decision") == "geometry_repaired_rows_ready_for_scorer_audit",
        "repaired_rows_measurable": geometry.get("decision") == "repaired_rows_are_measurable_but_need_guarded_overfit_diagnostic",
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "expanded_web_fail_to_pass_support_ready_for_guarded_package_builder" if all(gates.values()) else "expanded_web_fail_to_pass_support_not_ready",
        "selected_frontier_remains": {
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
        },
        "expanded_support_status": {
            "admitted_roots": executor.get("total_admitted_roots"),
            "rejected_roots": executor.get("total_rejected_roots"),
            "train_rows": rows.get("train_rows"),
            "admitted_rows": anticheat.get("admitted_rows"),
            "complete_six_task_roots": anticheat.get("complete_six_task_roots"),
            "task_counts": repair.get("task_counts"),
            "target_role_counts": repair.get("target_role_counts"),
            "rejection_blockers": executor.get("rejection_blockers"),
        },
        "scorer_geometry_on_repaired_rows": {
            "stage11507_selected": compact.get("stage11507_selected"),
            "stage11617_rejected": compact.get("stage11617_rejected"),
            "interpretation": "Rows are measurable after repair, but selected product scorer remains weak on them; a guarded training package is required before any frontier claim.",
        },
        "gates": gates,
        "next_actions": [
            "Build a guarded package from the 48 repaired rows plus protected canaries and Web heldout, not a same-row overfit.",
            "Use stronger but conservative Web-head optimization with preservation KL; do not reuse the 1024-step overfit settings directly.",
            "Promotion still requires residual >=7/10, filtered strict 22/22, old strict 23/23, and Web heldout >35/66.",
            "Continue materializing more Llama/OpenHands roots if the guarded package does not move heldout.",
        ],
        "source_artifacts": {
            "executor": rel(EXECUTOR),
            "rows": rel(ROWS),
            "anti_cheat": rel(ANTICHEAT),
            "repair": rel(REPAIR),
            "geometry": rel(GEOMETRY),
            "selected_runtime": rel(SELECTED_RUNTIME),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "claim_boundary": [
            "This stage reports expanded controlled train-support readiness only.",
            "No frontier model is promoted.",
            "Controlled mutation rows remain non-headline, train-support-only material.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "expanded_support_status": summary["expanded_support_status"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
