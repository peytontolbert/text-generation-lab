from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9954_blended_edit_localization_same_manifest_comparison_gate.py"
    spec = importlib.util.spec_from_file_location("stage9954", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_gate_preserves_same_manifest_row_contract():
    mod = _load()
    gate = mod.build_gate()
    assert gate["passed"] is True
    assert gate["row_contract"]["hundred_m_rows"] == 72
    assert gate["row_contract"]["gemma_rows"] == 72
    assert gate["row_contract"]["hundred_m_web_rows"] == 27
    assert gate["row_contract"]["gemma_web_rows"] == 27


def test_gate_requires_future_same_manifest_only_after_both_outputs():
    mod = _load()
    gate = mod.build_gate()
    assert gate["metrics"]["comparison_ready_now"] is False
    assert gate["gate_rows"]["future_stage_100m"] == 9950
    assert gate["gate_rows"]["future_gemma_ready_when_authorized"] is True
    assert "stage9950_output_acceptance_ready" in gate["gate_rows"]["same_manifest_claim_permitted_only_after"]
