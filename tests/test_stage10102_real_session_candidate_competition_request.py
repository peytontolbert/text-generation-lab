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


def test_stage10102_candidate_competition_request_builds() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10102_real_session_candidate_competition_request.py",
        "stage10102",
    )
    request, rows = mod.build()
    assert request["passed"] is True
    assert len(rows) == 39
    assert request["metrics"]["template_counts"] == {
        "cpp_file_vs_file": 4,
        "python_file_vs_test": 30,
        "web_entrypoint_vs_file": 5,
    }
    assert request["claim_boundary"]["bootstrap_candidate_competition_ready_for_python_c_cpp_web"] is True
    assert request["claim_boundary"]["rust_replenishment_required"] is True
    assert request["claim_boundary"]["four_language_maintainer_claim_ready"] is False
