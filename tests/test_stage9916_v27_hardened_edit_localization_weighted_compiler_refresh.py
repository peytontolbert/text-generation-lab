from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9916_v27_hardened_edit_localization_weighted_compiler_refresh.py"
    spec = importlib.util.spec_from_file_location("stage9916", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9916_only_duplicates_edit_localization_train_rows():
    mod = _load()
    prepared, failures = mod.build_prepared_rows()
    assert failures == []
    edit_train = [
        row for row in prepared
        if str(row.get("source_skill_area") or "") == "edit_localization" and str(row.get("split") or "") == "train"
    ]
    edit_eval = [
        row for row in prepared
        if str(row.get("source_skill_area") or "") == "edit_localization" and str(row.get("split") or "") == "eval"
    ]
    weighted = [row for row in edit_train if row.get("duplication_role") == "edit_localization_train_weight"]
    assert len(edit_train) == 32
    assert len(edit_eval) == 16
    assert len(weighted) == 16
    assert all("train_weight_dup" in str(row.get("row_id")) for row in weighted)
