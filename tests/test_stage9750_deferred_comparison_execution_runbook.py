from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9750_deferred_comparison_execution_runbook.py"
    spec = importlib.util.spec_from_file_location("stage9750", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9750_runbook_detects_runner_gap():
    mod = _load()
    runbook = mod.build_runbook()
    assert runbook["failures"] == []
    assert runbook["runner_surfaces"]["target_100m_probe_trainer"]["exists"] is True
    assert runbook["runner_surfaces"]["target_100m_probe_trainer"]["supports_target_100m_probe_execution"] is True
    assert runbook["runner_surfaces"]["target_100m_probe_trainer"]["exposes_gemma_flag"] is False
    assert runbook["runner_surfaces"]["target_100m_probe_trainer"]["exposes_harness_flag"] is False
    assert runbook["runner_surfaces"]["standalone_gemma_runner_present"] is False
    assert runbook["runner_surfaces"]["full_product_harness_runner_present"] is False
    assert runbook["execution_fronts"]["standalone_same_surface_comparison"]["queue_entries"] == 13
    assert runbook["execution_fronts"]["full_product_harness_comparison"]["queue_entries"] == 36
