from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9778_multilingual_training_readiness_audit.py"
    spec = importlib.util.spec_from_file_location("stage9778", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9778_records_honest_training_readiness():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["ready_surfaces"] == ["symbol_binding", "edit_localization_visible_evidence"]
    assert audit["blocked_surfaces"] == ["patch_operator_selection", "verifier_failure_repair_or_abstain"]
    assert audit["winning_surfaces"] == ["edit_localization_visible_evidence"]
    patch = next(surface for surface in audit["surfaces"] if surface["surface"] == "patch_operator_selection")
    verifier = next(surface for surface in audit["surfaces"] if surface["surface"] == "verifier_failure_repair_or_abstain")
    assert patch["ready_for_training"] is False
    assert verifier["ready_for_training"] is False
    assert patch["separable_only_with_leaky_fields_bucket_count"] == 12
    assert verifier["separable_only_with_leaky_fields_bucket_count"] == 12
