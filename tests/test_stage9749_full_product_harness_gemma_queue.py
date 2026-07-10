from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9749_full_product_harness_gemma_queue.py"
    spec = importlib.util.spec_from_file_location("stage9749", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9749_builds_harness_queue():
    mod = _load()
    queue = mod.build_queue()
    assert queue["failures"] == []
    assert queue["metrics"]["queue_entries"] == 36
    assert queue["metrics"]["priority_buckets"] == {
        "aligned_with_supported_standalone_cell": 13,
        "no_standalone_proxy_support_yet": 23,
    }
    assert queue["metrics"]["languages"] == {
        "c_cpp": 9,
        "python": 9,
        "rust": 9,
        "web_js_ts_html": 9,
    }
    assert queue["metrics"]["skills"] == {
        "bounded_argument_rendering": 4,
        "edit_localization": 4,
        "final_user_facing_summary": 4,
        "intent_to_build_strategy": 4,
        "patch_operator_selection": 4,
        "repo_state_graph_navigation": 4,
        "symbol_binding": 4,
        "verifier_expectation": 4,
        "verifier_failure_repair_or_abstain": 4,
    }
    assert queue["metrics"]["top_queue_entry"] == "full_product_harness::python::symbol_binding"
