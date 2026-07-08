from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9260_stage9253_postrun_diagnostic_audit.py"
    spec = importlib.util.spec_from_file_location("stage9260", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9253_postrun_audit_classifies_safe_execution_but_quality_failure():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["execution_safety_passed"] is True
    assert audit["probe_quality_passed"] is False
    assert audit["metrics"]["decoder_quality_passed"] is False
    assert audit["metrics"]["generated_rows"] == 16
    assert audit["metrics"]["contentful_generation_rate"] == 0.0
    assert audit["metrics"]["checkpoint_like_artifacts"] == 0
    assert audit["metrics"]["structured_head_delta_norm"] == 0.0


def test_required_artifact_card_has_no_missing_or_empty_outputs():
    mod = _load()
    card = mod.artifact_card()
    assert card["missing_artifacts"] == []
    assert card["empty_artifacts"] == []
    assert card["checkpoint_like_artifacts"] == []
