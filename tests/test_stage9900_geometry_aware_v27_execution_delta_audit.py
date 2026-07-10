from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9900_geometry_aware_v27_execution_delta_audit.py"
    spec = importlib.util.spec_from_file_location("stage9900", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9900_captures_execution_improvement_on_symbol_binding_and_edit_localization():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    delta = audit["metrics"]["surface_delta"]
    assert delta["symbol_binding"]["delta_eval_exact"] > 0
    assert delta["edit_localization"]["delta_eval_exact"] > 0
    assert delta["patch_operator_selection"]["delta_eval_exact"] == 0.0
    assert delta["verifier_failure_repair_or_abstain"]["delta_eval_exact"] == 0.0
