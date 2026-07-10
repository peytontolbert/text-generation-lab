from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9756_full_product_harness_review_packets.py"
    spec = importlib.util.spec_from_file_location("stage9756", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9756_materializes_harness_review_packets():
    mod = _load()
    built = mod.build_review_packets(mod.load_json(mod.QUEUE), mod.load_json(mod.RUNBOOK))
    metrics = built["metrics"]
    packets = built["review_packets"]
    assert built["failures"] == []
    assert metrics["review_packets"] == 36
    assert metrics["review_packets_with_harness_slots"] == 36
    assert metrics["review_packets_with_rubric_slots"] == 36
    assert metrics["review_packets_with_anticheat_slots"] == 36
    assert metrics["priority_buckets"] == {
        "aligned_with_supported_standalone_cell": 13,
        "no_standalone_proxy_support_yet": 23,
    }
    first = packets[0]
    assert first["cell_key"] == "full_product_harness::python::symbol_binding"
    assert first["runner_status"] == "missing_harness_runner_surface"
    assert first["harness_execution_template"]["required_artifacts"] == [
        "harness_run_id",
        "same_task_pack_as_gemma12b",
        "tool_trace_spans",
        "verifier_results",
        "patch_minimality_or_abstain_scores",
        "expert_maintainer_rubric_scores",
        "anti_cheat_cards",
    ]
    assert first["merge_ready_bundle_template"]["mode"] == "full_product_harness"
    assert first["merge_ready_bundle_template"]["anti_cheat_attachment"]["stage9717_gate_passed"] is True
    assert first["merge_ready_bundle_template"]["evidence_artifacts"]["harness_run_id"] is None
