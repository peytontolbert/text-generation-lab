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


def test_stage10103_bootstrap_packet_builds() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10103_real_session_candidate_competition_bootstrap_packet.py",
        "stage10103",
    )
    audit, rows, drops = mod.build()
    assert audit["passed"] is True
    assert len(rows) == 33
    assert len(drops) == 6
    assert audit["metrics"]["template_counts"] == {
        "cpp_file_vs_file": 3,
        "python_file_vs_test": 30,
    }
    assert audit["metrics"]["all_materialized_rows_use_opaque_candidate_ids"] is True
    assert audit["claim_boundary"]["supports_training_or_scoring_now"] is False
    assert audit["claim_boundary"]["gold_labels_still_missing"] is True
    assert audit["claim_boundary"]["web_rows_underpowered_after_materialization"] is True
