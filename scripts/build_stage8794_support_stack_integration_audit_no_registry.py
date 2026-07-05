#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8794
NAME = "stage8794_support_stack_integration_audit_no_registry"
SOURCE = ROOT / "runs/summaries/stage8753_parallel_recovery_gap_audit.json"
GRAPH = ROOT / "runs/local/artifacts/stage8793_query_recovery_graph_attachment/central_research_graph_with_query_recovery.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORT_STACK_INTEGRATION_AUDIT_NO_REGISTRY_STAGE8794.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}
EXPECTED_SUMMARY_OVERRIDES = {
    "schema_drift_detector": ["stage8754_schema_drift_detector_readiness"],
    "patch_minimality_complexity_meter": ["stage8756_patch_minimality_complexity_meter_readiness"],
    "coverage_test_selection": ["stage8757_coverage_test_selection_readiness"],
    "flaky_test_detector": ["stage8758_flaky_test_detector_readiness"],
    "eval_trace_to_dataset_patch_loop": ["stage8768_eval_trace_to_dataset_patch_loop_v2_readiness", "stage8760_eval_trace_to_dataset_patch_loop_readiness"],
    "skill_tool_registry": ["stage8769_skill_tool_registry_readiness"],
    "ngram_repetition_style_detectors": ["stage8771_ngram_repetition_style_detectors_readiness"],
    "memory_retrieval_evaluator": ["stage8772_memory_retrieval_evaluator_readiness"],
    "cost_budget_scheduler": ["stage8777_cost_budget_scheduler_readiness"],
    "static_analysis_security_scanner": ["stage8778_static_analysis_security_scanner_readiness"],
    "weak_supervision_label_model": ["stage8780_weak_supervision_label_model_readiness"],
    "knowledge_graph_memory_store": ["stage8781_knowledge_graph_memory_store_readiness"],
    "latency_resource_observability": ["stage8783_latency_resource_observability_readiness"],
    "repository_universe_builder": ["stage8784_repository_universe_builder_readiness"],
    "traced_eval_observability": ["stage8786_traced_eval_observability_readiness"],
    "query_expansion_rewriter": ["stage8791_query_expansion_rewriter_readiness"],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def matching_summaries(module_id: str) -> list[Path]:
    names = EXPECTED_SUMMARY_OVERRIDES.get(module_id, [module_id])
    matches: list[Path] = []
    for path in (ROOT / "runs/summaries").glob("stage87*_*.json"):
        stem = path.stem
        if any(name in stem for name in names):
            matches.append(path)
    return sorted(matches)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE)
    graph = load_json(GRAPH)
    graph_ids = {node.get("id") for node in graph.get("nodes", [])}
    module_records = [r for r in source.get("records", []) if r.get("effective_status") == "missing_real"]

    records = []
    test_files = []
    for record in module_records:
        module_id = str(record["module_id"])
        required_files = list(record.get("files", []))
        missing_files = [rel for rel in required_files if not (ROOT / rel).exists()]
        test_files.extend(rel for rel in required_files if rel.startswith("tests/") and (ROOT / rel).exists())
        summaries = matching_summaries(module_id)
        summary_cards = [load_json(path) for path in summaries]
        failed_summaries = [card.get("stage_name") for card in summary_cards if card and card.get("passed") is not True]
        graph_present = f"support_module:{module_id}" in graph_ids
        records.append({
            "module_id": module_id,
            "missing_files": missing_files,
            "readiness_summaries": [str(path.relative_to(ROOT)) for path in summaries],
            "failed_summaries": [name for name in failed_summaries if name],
            "graph_present": graph_present,
            "ready_local": not missing_files and bool(summaries) and not failed_summaries,
        })

    unique_tests = sorted(set(test_files))
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", *unique_tests], cwd=ROOT, text=True, capture_output=True, check=False)
    missing_files = [row for row in records if row["missing_files"]]
    missing_readiness = [row for row in records if not row["readiness_summaries"]]
    failed_readiness = [row for row in records if row["failed_summaries"]]
    missing_graph = [row for row in records if not row["graph_present"]]
    blockers = []
    if missing_files:
        blockers.append("missing_files")
    if missing_readiness:
        blockers.append("missing_readiness_summaries")
    if failed_readiness:
        blockers.append("failed_readiness_summaries")
    if missing_graph:
        blockers.append("missing_graph_nodes")
    if test.returncode != 0:
        blockers.append("focused_tests_failed")

    records_path = OUT_DIR / "support_stack_integration_records.json"
    records_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not blockers,
        "audit_result": "integration_ready_no_registry" if not blockers else "integration_blocked_no_registry",
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "modules_reviewed": len(records),
            "ready_local_modules": sum(1 for row in records if row["ready_local"]),
            "missing_file_modules": len(missing_files),
            "missing_readiness_modules": len(missing_readiness),
            "failed_readiness_modules": len(failed_readiness),
            "missing_graph_modules": len(missing_graph),
            "focused_tests": len(unique_tests),
            "focused_tests_returncode": test.returncode,
            "blockers": blockers,
        },
        "records": records,
        "artifacts": {
            "records": str(records_path.relative_to(ROOT)),
            "graph": str(GRAPH.relative_to(ROOT)),
            "source_gap_audit": str(SOURCE.relative_to(ROOT)),
        },
        "decision": (
            "Recovered support stack is integrated in the Stage8793 graph at no-registry/no-training level."
            if not blockers
            else "Recovered support stack still has integration blockers."
        ),
        "next_best_step": "Reconcile reconstructed registry and central spine in one controlled pass; keep mining/training closed until that pass is clean.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8794 Support Stack Integration Audit No Registry",
        "",
        f"Audit result: `{card['audit_result']}`",
        "",
        f"Modules reviewed: `{card['metrics']['modules_reviewed']}`",
        f"Ready local modules: `{card['metrics']['ready_local_modules']}`",
        f"Missing graph modules: `{card['metrics']['missing_graph_modules']}`",
        f"Focused tests: `{card['metrics']['focused_tests']}` with return code `{test.returncode}`",
        f"Blockers: `{blockers}`",
        "",
        "This audit intentionally does not update the reconstructed registry. Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
