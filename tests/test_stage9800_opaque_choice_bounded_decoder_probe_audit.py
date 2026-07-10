from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9800_opaque_choice_bounded_decoder_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9800", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9800_reports_single_label_collapse():
    mod = _load()
    audit = mod.build_audit()
    assert audit["generated_rows"] == 20
    assert audit["valid_label_rows"] == 20
    assert audit["exact_match_rows"] == 4
    assert audit["dominant_label"] == "C"
    assert audit["dominant_label_rows"] == 20
    assert audit["collapsed_single_label"] is True
    assert audit["passed"] is False
