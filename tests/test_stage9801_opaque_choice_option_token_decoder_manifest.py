from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9801_opaque_choice_option_token_decoder_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9801", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9801_builds_option_token_decoder_manifest():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.audit_rows(rows)
    assert audit["passed"] is True
    assert audit["rows"] == 60
    assert audit["decoder_text_counts"] == {
        "option A": 12,
        "option B": 12,
        "option C": 12,
        "option D": 12,
        "option E": 12,
    }

