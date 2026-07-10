from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9781_winning_edit_localization_state_hash.py"
    spec = importlib.util.spec_from_file_location("stage9781", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9781_updates_four_checkpoint_slots_from_hash_card():
    mod = _load()
    fake_hash_card = {
        "state_sha256": "abc123",
        "manifest_sha256": "def456",
        "best_state_restored": True,
        "selected_step": 64,
    }
    updates = mod._update_checkpoint_slots(fake_hash_card)
    assert len(updates) == 4

    root = Path(__file__).resolve().parents[1]
    sample = next(item for item in updates if item["cell_key"] == "standalone_100m_weights::python::edit_localization")
    text = (root / sample["checkpoint_path"]).read_text(encoding="utf-8")
    assert "status=frozen_runtime_state_hash_recorded" in text
    assert "frozen_runtime_state_sha256=abc123" in text
    assert "selected_step=64" in text
