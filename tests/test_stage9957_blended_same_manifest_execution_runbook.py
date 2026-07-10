from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9957_blended_same_manifest_execution_runbook.py"
    spec = importlib.util.spec_from_file_location("stage9957", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_runbook_links_future_stages_and_claim_rule():
    mod = _load()
    built = mod.build_runbook()
    assert built["passed"] is True
    assert built["metrics"]["hundred_m_future_stage"] == 9950
    assert built["metrics"]["gemma_future_stage"] == 9953
    assert built["metrics"]["claim_rule_present"] is True


def test_runbook_contains_ordered_execution_steps():
    mod = _load()
    built = mod.build_runbook()
    step_ids = [row["step_id"] for row in built["steps"]]
    assert step_ids == [
        "precheck_authorization_and_disk",
        "run_stage9950_hundred_m",
        "audit_stage9950_outputs",
        "run_stage9953_gemma",
        "compare_same_manifest_only",
    ]
