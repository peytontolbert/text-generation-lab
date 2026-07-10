from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9888_current_margin_position_bias_diagnostics.py"
    spec = importlib.util.spec_from_file_location("stage9888", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9888_detects_source_skew_and_builds_broader_position_support():
    mod = _load()
    rows = mod.read_jsonl(mod.MANIFEST)
    position = mod.position_stats(rows)
    debiased_rows, debiased = mod.build_position_debiased_rows(rows)
    assert len(debiased_rows) == len(rows) == 48
    assert position["every_target_spans_at_least_three_positions"] is False
    assert debiased["every_target_spans_at_least_three_positions"] is True
    assert debiased["every_semantic_surface_spans_at_least_three_positions"] is True
    assert len(debiased["target_position_counts"]["K"]) >= 3
