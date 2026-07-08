from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9262_bounded_decoder_stabilization_trainer_patch_audit.py"
    spec = importlib.util.spec_from_file_location("stage9262", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9262_static_audit_sees_stabilization_patch():
    mod = _load()
    audit = mod.audit_patch()
    assert audit["passed"] is True
    assert audit["help_has_eos_loss_weight"] is True
    assert audit["py_compile_passed"] is True
    assert all(audit["snippet_results"].values())
    assert audit["model_execution_attempted"] is False
    assert audit["training_attempted"] is False
