from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9797_opaque_choice_bounded_decoder_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9797", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9797_builds_decoder_manifest_from_stage9790():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.audit_rows(rows)
    assert audit["passed"] is True
    assert audit["rows"] == 60
    assert audit["split_counts"] == {"eval": 20, "strict_eval": 20, "train": 20}
    assert audit["language_counts"] == {"c_cpp": 15, "python": 15, "rust": 15, "web_js_ts_html": 15}
    assert audit["decoder_label_counts"] == {"A": 12, "B": 12, "C": 12, "D": 12, "E": 12}

