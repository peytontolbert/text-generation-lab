from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9806_opaque_choice_error_atlas.py"
    spec = importlib.util.spec_from_file_location("stage9806", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9806_builds_four_language_error_atlas():
    mod = _load()
    atlas = mod.build_atlas()
    assert atlas["passed"] is True
    assert atlas["metrics"]["language_slices"] == 4
    assert atlas["metrics"]["winning_languages"] == 3
    assert atlas["metrics"]["tied_languages"] == 1
    web = next(row for row in atlas["languages"] if row["language_family"] == "web_js_ts_html")
    assert web["strict_exact_100m"] == 0.2
    assert web["strict_exact_gemma12b"] == 0.2
    assert web["same_surface_verdict"] == "tie"
    assert len(web["wrong_rows"]) == 4
    assert web["recommendation"]["next_modeling_move"] == "augment_web_visible_evidence_with_surface_disambiguators"
