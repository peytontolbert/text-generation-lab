from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage10009_quarantined_blended_v27_mix.py"
    spec = importlib.util.spec_from_file_location("stage10009", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_normalize_review_row_id_strips_stage9961_prefix_only():
    mod = _load()
    assert mod.normalize_review_row_id("stage9961_example") == "example"
    assert mod.normalize_review_row_id("stage9857_example") == "stage9857_example"


def test_unresolved_review_rows_deduplicates_prefixed_aliases():
    mod = _load()
    raw_ids, normalized_ids = mod.unresolved_review_rows(
        [
            {"row_id": "stage9857_row_a"},
            {"row_id": "stage9961_stage9857_row_a"},
            {"row_id": "stage9857_row_b"},
        ]
    )
    assert raw_ids == {"stage9857_row_a", "stage9961_stage9857_row_a", "stage9857_row_b"}
    assert normalized_ids == {"stage9857_row_a", "stage9857_row_b"}


def test_build_quarantined_mix_matches_expected_open_row_quarantine_counts():
    mod = _load()
    built = mod.build_quarantined_mix()
    assert built["passed"] is True
    assert built["metrics"]["source_blended_rows"] == 404
    assert built["metrics"]["rows_removed_from_active_blend"] == 8
    assert built["metrics"]["rows_remaining_after_quarantine"] == 396
    assert built["metrics"]["removed_language_counts"] == {"c_cpp": 3, "python": 5}
    assert built["metrics"]["removed_split_counts"] == {"eval": 3, "strict_eval": 5}
    assert built["metrics"]["removed_skill_counts"] == {"edit_localization": 8}
