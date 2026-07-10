from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9903_current_margin_locality_signal_neutral_label_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9903", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9903_uses_neutral_a_to_d_vocab():
    mod = _load()
    rows = mod.read_jsonl(mod.SOURCE_MANIFEST)
    remapped, audit = mod.build_rows(rows)
    assert len(remapped) == len(rows) == 48
    assert audit["target_labels"] == ["A", "B", "C", "D"]
    assert audit["uses_neutral_a_to_d_vocab"] is True
    assert remapped[0]["anti_cheat"]["stage9904_neutral_label_inventory"] == ["A", "B", "C", "D"]
