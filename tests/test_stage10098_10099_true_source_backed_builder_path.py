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


def test_stage10098_synthetic_ancestry_audit_builds() -> None:
    mod = _load(ROOT / 'scripts/build_stage10098_locked_source_subset_synthetic_ancestry_audit.py', 'stage10098')
    built = mod.build()
    assert built['passed'] is True
    assert built['metrics']['locked_rows'] == 18
    assert built['metrics']['stage8765_ancestry_matches'] == 18
    assert built['claim_boundary']['replacement_builder_required'] is True
    assert built['claim_boundary']['locked_subset_is_true_maintainer_eval'] is False


def test_stage10099_builder_request_builds() -> None:
    stage10098 = _load(ROOT / 'scripts/build_stage10098_locked_source_subset_synthetic_ancestry_audit.py', 'stage10098_req')
    packet = stage10098.build()
    stage10098.write_json(stage10098.PACKET, packet)
    mod = _load(ROOT / 'scripts/build_stage10099_true_source_backed_edit_localization_builder_request.py', 'stage10099')
    request = mod.build()
    assert request['passed'] is True
    assert request['claim_boundary']['true_source_backed_builder_required_now'] is True
    assert request['claim_boundary']['current_stage8765_path_salvageable_for_maintainer_claim'] is False
