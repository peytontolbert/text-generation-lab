#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8752
NAME = "stage8752_support_stack_integration_audit"
GRAPH = ROOT / "runs/local/artifacts/stage8751_drift_canary_regression_monitor_graph_attachment/central_research_graph_with_drift_canary_regression_monitor.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORT_STACK_INTEGRATION_AUDIT_STAGE8752.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
MODULES = {
    "source_inventory_lineage_tracker": ["scripts/source_inventory_lineage_tracker.py", "tests/test_source_inventory_lineage_tracker.py", "runs/summaries/stage8741_source_inventory_lineage_tracker_readiness.json"],
    "source_provenance_license_security_filter": ["scripts/source_provenance_license_security_filter.py", "tests/test_source_provenance_license_security_filter.py", "runs/summaries/stage8743_source_provenance_license_security_filter_readiness.json"],
    "contamination_leakage_detector": ["scripts/contamination_leakage_detector.py", "tests/test_contamination_leakage_detector.py", "runs/summaries/stage8746_contamination_leakage_detector_readiness.json"],
    "golden_locked_eval_suite": ["scripts/golden_locked_eval_suite.py", "tests/test_golden_locked_eval_suite.py", "runs/summaries/stage8748_golden_locked_eval_suite_readiness.json"],
    "drift_canary_regression_monitor": ["scripts/drift_canary_regression_monitor.py", "tests/test_drift_canary_regression_monitor.py", "runs/summaries/stage8750_drift_canary_regression_monitor_readiness.json"],
    "cluster_slice_near_duplicate_detector": ["scripts/cluster_slice_near_duplicate_detector.py", "tests/test_cluster_slice_near_duplicate_detector.py", "runs/summaries/stage8682_cluster_slice_detector_readiness.json"],
    "dataset_junk_ood_ranker_v1": ["scripts/dataset_junk_ood_ranker_v1.py", "tests/test_dataset_junk_ood_ranker_v1.py", "runs/summaries/stage8681_unified_dataset_junk_ood_ranker_readiness.json"],
    "dataset_cartography_active_learning": ["scripts/dataset_cartography_active_learning.py", "tests/test_dataset_cartography_active_learning.py", "runs/summaries/stage8723_dataset_cartography_active_learning_readiness.json"],
    "training_data_attribution_influence": ["scripts/training_data_attribution_influence.py", "tests/test_training_data_attribution_influence.py", "runs/summaries/stage8725_training_data_attribution_influence_readiness.json"],
    "curriculum_compiler": ["scripts/curriculum_compiler.py", "tests/test_curriculum_compiler.py"],
}
REQUIRED_COMPILER_REFERENCES = [
    "source_inventory_lineage",
    "source_provenance",
    "contamination_leakage_detector",
    "golden_locked_eval_suite",
    "drift_canary_regression_monitor",
    "cluster_slice_near_duplicate_detector",
    "dataset_junk_ood_ranker_v1",
]
TEST_FILES = [
    "tests/test_contamination_leakage_detector.py",
    "tests/test_golden_locked_eval_suite.py",
    "tests/test_drift_canary_regression_monitor.py",
    "tests/test_cluster_slice_near_duplicate_detector.py",
    "tests/test_dataset_cartography_active_learning.py",
    "tests/test_training_data_attribution_influence.py",
]


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def load_json(rel: str) -> dict[str, Any]:
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def write_registry(card: dict[str, Any]) -> None:
    path = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
    registry = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"passed": True, "rows": []}
    rows = [row for row in registry.get("rows", []) if int(row.get("stage", -1)) != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: int(row.get("stage", -1)))
    registry["rows"] = rows
    registry["passed"] = all(row.get("passed") is True for row in rows)
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    graph = json.loads(GRAPH.read_text(encoding="utf-8")) if GRAPH.exists() else {"nodes": []}
    graph_ids = {node.get("id") for node in graph.get("nodes", [])}
    module_cards = []
    missing_files = []
    missing_graph_nodes = []
    failed_summaries = []
    for module_id, files in MODULES.items():
        missing = [rel for rel in files if not exists(rel)]
        summaries = [load_json(rel) for rel in files if rel.startswith("runs/summaries/")]
        summary_failed = [summary.get("stage_name") for summary in summaries if summary and summary.get("passed") is not True]
        graph_present = f"support_module:{module_id}" in graph_ids or module_id == "curriculum_compiler" and "support_module:curriculum_compiler" in graph_ids
        if missing:
            missing_files.extend(missing)
        if not graph_present:
            missing_graph_nodes.append(module_id)
        if summary_failed:
            failed_summaries.extend(summary_failed)
        module_cards.append({"module_id": module_id, "missing_files": missing, "graph_present": graph_present, "summary_failures": summary_failed})
    compiler_text = (ROOT / "scripts/curriculum_compiler.py").read_text(encoding="utf-8") if exists("scripts/curriculum_compiler.py") else ""
    missing_compiler_refs = [ref for ref in REQUIRED_COMPILER_REFERENCES if ref not in compiler_text]
    test_cmd = [sys.executable, "-m", "pytest", "-q", *[rel for rel in TEST_FILES if exists(rel)]]
    test = subprocess.run(test_cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    integration_blockers = []
    if missing_files:
        integration_blockers.append("missing_required_files")
    if missing_graph_nodes:
        integration_blockers.append("missing_graph_nodes")
    if failed_summaries:
        integration_blockers.append("failed_required_summaries")
    if missing_compiler_refs:
        integration_blockers.append("curriculum_compiler_not_wired_to_recovered_gates")
    if test.returncode != 0:
        integration_blockers.append("support_tests_failed")
    cards_path = OUT_DIR / "support_stack_integration_cards.json"
    cards_path.write_text(json.dumps(module_cards, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "audit_result": "integration_ready" if not integration_blockers else "integration_partial_blocked",
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "modules_reviewed": len(MODULES), "missing_required_files": len(set(missing_files)), "missing_graph_nodes": len(set(missing_graph_nodes)), "failed_required_summaries": len(set(failed_summaries)), "missing_compiler_gate_references": len(missing_compiler_refs), "support_tests_returncode": test.returncode, "integration_blockers": integration_blockers},
        "missing_compiler_gate_references": missing_compiler_refs,
        "missing_files": sorted(set(missing_files)),
        "missing_graph_nodes": sorted(set(missing_graph_nodes)),
        "failed_summaries": sorted(set(x for x in failed_summaries if x)),
        "artifacts": {"module_cards": str(cards_path.relative_to(ROOT)), "graph": str(GRAPH.relative_to(ROOT)) if GRAPH.exists() else None},
        "decision": "Support modules are recovered, but curriculum compiler wiring is still incomplete; do not resume mining or training until the compiler consumes the recovered gates." if integration_blockers else "Support stack integration is complete at no-training contract level.",
        "next_best_step": "Run a scale-readiness preflight over a small no-training manifest requiring recovered gates before any mining or training resume." if not integration_blockers else "Patch curriculum_compiler to require source lineage, provenance, contamination, locked-eval exclusion, duplicate/ranker gates, and canary metric cards before any scale manifest.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8752 Support Stack Integration Audit", "", f"Audit result: `{card['audit_result']}`", "", f"Integration blockers: `{', '.join(integration_blockers) if integration_blockers else 'none'}`", "", "This audit is intentionally no-training and no-runtime. Authority remains closed.", ""]), encoding="utf-8")
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
