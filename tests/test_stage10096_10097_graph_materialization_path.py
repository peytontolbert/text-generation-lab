from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10096_gap_audit_builds() -> None:
    mod = _load(ROOT / 'scripts/build_stage10096_locked_source_graph_materialization_gap_audit.py', 'stage10096')
    built = mod.build()
    assert built['passed'] is True
    assert built['metrics']['locked_rows'] == 18
    assert built['metrics']['matched_source_rows'] == 18
    assert built['metrics']['rows_with_source_graph_materialized_false'] == 18
    assert built['claim_boundary']['graph_materialization_bridge_required'] is True


def test_stage10097_bridge_request_builds() -> None:
    mod = _load(ROOT / 'scripts/build_stage10097_locked_source_graph_materialization_bridge_request.py', 'stage10097')
    request, rows = mod.build()
    assert request['passed'] is True
    assert request['metrics']['rows'] == 18
    assert request['metrics']['rows_with_opaque_query_ids'] == 18
    assert request['metrics']['rows_with_unmaterialized_graph'] == 18
    assert len(rows) == 18


def test_stage10097_languages_match_locked_subset() -> None:
    mod = _load(ROOT / 'scripts/build_stage10097_locked_source_graph_materialization_bridge_request.py', 'stage10097_langs')
    request, _ = mod.build()
    assert request['metrics']['languages'] == {'c_cpp': 12, 'python': 6}
