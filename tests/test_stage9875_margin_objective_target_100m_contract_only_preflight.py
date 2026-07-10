from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9875_margin_objective_target_100m_contract_only_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9875_mod", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9875_mod"] = module
    spec.loader.exec_module(module)
    return module


def test_stage9875_sources_stage9874_outputs():
    mod = _load()
    assert "stage9874_v27_margin_objective_multisurface_compiler_refresh" in str(mod.SOURCE_SUMMARY)
    assert "stage9874_v27_margin_objective_multisurface_compiler_refresh" in str(mod.STRUCTURED)
