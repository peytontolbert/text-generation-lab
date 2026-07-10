from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9735_multilingual_patch_operator_label_aligned_package.py"
    spec = importlib.util.spec_from_file_location("stage9735", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9735_selects_all_labels_for_all_languages_and_splits():
    mod = _load()
    rows = mod.load_jsonl(mod.SOURCE)
    selected, failures, labels = mod.select_rows(rows)
    assert failures == []
    assert len(labels) == 12
    assert len(selected) == 144
    counts = {}
    for row in selected:
        key = (row["language_family"], row["split"])
        counts[key] = counts.get(key, 0) + 1
    for lang in mod.LANGS:
        for split in mod.SPLITS:
            assert counts[(lang, split)] == 12
