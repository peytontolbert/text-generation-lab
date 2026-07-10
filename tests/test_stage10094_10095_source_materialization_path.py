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


def test_stage10094_recoverability_audit_builds() -> None:
    mod = _load(ROOT / 'scripts/build_stage10094_realistic_source_materialization_recoverability_audit.py', 'stage10094')
    built = mod.build()
    assert built['passed'] is True
    assert built['metrics']['request_rows'] == 55
    assert built['metrics']['locked_eval_source_rows'] == 18
    assert built['metrics']['unique_normalized_stage8765_roots'] == 32
    assert built['claim_boundary']['full_55_row_source_backed_materialization_ready_now'] is False
    assert built['metrics']['graph_sources_resolve_to_external_arxiv'] is True


def test_stage10095_locked_subset_request_builds() -> None:
    mod = _load(ROOT / 'scripts/build_stage10095_locked_source_realistic_successor_request.py', 'stage10095')
    request, rows = mod.build()
    assert request['passed'] is True
    assert request['metrics']['rows'] == 18
    assert request['claim_boundary']['locked_subset_candidate_ready'] is True
    assert len(rows) == 18


def test_stage10095_language_coverage_is_narrow() -> None:
    mod = _load(ROOT / 'scripts/build_stage10095_locked_source_realistic_successor_request.py', 'stage10095_langs')
    request, _ = mod.build()
    assert request['metrics']['languages'] == {'c_cpp': 12, 'python': 6}
