from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9771_edit_localization_visible_evidence_lift_package.py'
    spec = importlib.util.spec_from_file_location('stage9771', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9771_lifted_surface_improves_uniqueness_without_target_literals():
    mod = _load()
    source_rows = mod.load_jsonl(mod.SOURCE)
    lifted_rows = mod.lift_rows(source_rows)
    baseline = mod.summarize_surface_uniqueness(source_rows)
    lifted = mod.summarize_surface_uniqueness(lifted_rows)
    failures = mod.collect_failures(lifted_rows)
    assert failures == []
    assert baseline['python:strict_eval']['unique_surface_count'] == 1
    assert lifted['python:strict_eval']['unique_surface_count'] == 5
    assert lifted['rust:strict_eval']['unique_surface_count'] == 5
    assert lifted['c_cpp:strict_eval']['unique_surface_count'] == 5
    assert lifted['web_js_ts_html:strict_eval']['unique_surface_count'] == 5
