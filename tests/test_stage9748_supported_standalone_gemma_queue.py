from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9748_supported_standalone_gemma_queue.py"
    spec = importlib.util.spec_from_file_location("stage9748", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9748_builds_supported_queue():
    mod = _load()
    queue = mod.build_queue()
    assert queue["failures"] == []
    assert queue["metrics"]["queue_entries"] == 13
    assert queue["metrics"]["languages"] == {
        "c_cpp": 3,
        "python": 4,
        "rust": 3,
        "web_js_ts_html": 3,
    }
    assert queue["metrics"]["skills"] == {
        "edit_localization": 4,
        "patch_operator_selection": 4,
        "symbol_binding": 1,
        "verifier_failure_repair_or_abstain": 4,
    }
    assert queue["metrics"]["top_queue_entry"] == "standalone_100m_weights::python::symbol_binding"
    assert queue["metrics"]["top_priority_score"] == 0.3125
