from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9910_geometry_aware_opaque_choice_shortcut_audit.py"
    spec = importlib.util.spec_from_file_location("stage9910", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9910"] = module
    spec.loader.exec_module(module)
    return module


def test_stage9910_build_audit_confirms_no_prompt_label_line():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["validated_buckets"] == 8
    assert audit["metrics"]["buckets_with_prompt_label_vocab_exposed"] == 0
    assert audit["metrics"]["unique_permutation_maps"] >= 4
    assert audit["gate_recommendation"]["same_surface_claim_hardened"] is True
