from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9804_opaque_choice_option_token_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9804", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9804_reports_option_token_single_label_collapse_without_junk():
    mod = _load()
    audit = mod.build_audit()
    assert audit["generated_rows"] == 40
    assert audit["exact_match_rows"] == 8
    assert audit["dominant_label"] == "option A"
    assert audit["dominant_label_rows"] == 40
    assert audit["collapsed_single_label"] is True
    assert audit["contentful_rate"] == 1.0
    assert audit["short_or_junk_rate"] == 0.0
    assert audit["passed"] is False
