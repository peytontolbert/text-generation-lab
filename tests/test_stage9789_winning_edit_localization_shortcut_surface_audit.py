from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9789_winning_edit_localization_shortcut_surface_audit.py"
    spec = importlib.util.spec_from_file_location("stage9789", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9789_finds_label_vocab_exposure_on_all_winning_cells():
    mod = _load()
    built = mod.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["validated_cells"] == 4
    assert built["metrics"]["cells_with_prompt_label_vocab_exposed"] == 4
    assert built["metrics"]["cells_with_clean_opaque_ids"] == 4


def test_stage9789_python_cell_is_not_opaque_label_clean():
    mod = _load()
    built = mod.build_audit()
    row = next(item for item in built["records"] if item["cell_key"] == "standalone_100m_weights::python::edit_localization")
    assert row["anti_cheat_gate_recommendation"]["opaque_label_surface_clean"] is False
    assert row["anti_cheat_gate_recommendation"]["label_proxy_shortcuts_pass_recommended"] is False
    assert row["metrics"]["prompt_rows_with_valid_label_line"] == 5
    assert row["metrics"]["identifier_records_with_target_mentions"] == 0
