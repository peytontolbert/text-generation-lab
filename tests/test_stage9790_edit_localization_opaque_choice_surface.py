from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9790_edit_localization_opaque_choice_surface.py"
    spec = importlib.util.spec_from_file_location("stage9790", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9790_builds_opaque_choice_surface_without_target_literals():
    mod = _load()
    audit = mod.build_surface()
    assert audit["passed"] is True
    assert audit["rows"] == 60
    assert audit["failures"] == []
    assert set(audit["decoder_label_counts"]) == set(mod.OPAQUE_LABELS)
    assert sum(audit["decoder_label_counts"].values()) == 60


def test_stage9790_python_strict_rows_use_opaque_decoder_targets_and_permuted_choices():
    mod = _load()
    rows = mod.load_jsonl(mod.MANIFEST)
    python_strict = [row for row in rows if row["language_family"] == "python" and row["split"] == "strict_eval"]
    assert len(python_strict) == 5
    assert all((row.get("target") or {}).get("decoder_text") in mod.OPAQUE_LABELS for row in python_strict)
    assert all("TARGET_" not in mod._row_text(row) for row in python_strict)
    choice_orders = {tuple((row.get("input_state") or {}).get("candidate_choices") or []) for row in python_strict}
    assert len(choice_orders) == 1
    assert len({(row.get("target") or {}).get("decoder_text") for row in python_strict}) == 5


def test_stage9790_python_choice_order_is_stable_across_splits():
    mod = _load()
    rows = mod.load_jsonl(mod.MANIFEST)
    python_rows = [row for row in rows if row["language_family"] == "python"]
    choice_orders = {
        row["split"]: tuple((row.get("input_state") or {}).get("candidate_choices") or [])
        for row in python_rows
    }
    assert choice_orders["train"] == choice_orders["eval"] == choice_orders["strict_eval"]
