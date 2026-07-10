from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9905_current_margin_locality_signal_neutral_label_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9905", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9905_paths_target_stage9904_and_comparison_controls():
    mod = _load()
    assert "stage9904_current_margin_locality_signal_neutral_label_target_100m_probe" in str(mod.PROBE_DIR)
    assert "stage9892_current_margin_locality_signal_lift_target_100m_probe" in str(mod.PRIOR_EXECUTION)
    assert "stage9894_current_margin_locality_signal_label_remap_target_100m_probe" in str(mod.REMAP_EXECUTION)


def test_stage9905_pred_counts_accumulate_confusion_rows():
    mod = _load()
    confusion = {"edit_localization": {"A": {"A": 2, "B": 1}, "B": {"B": 3}, "C": {"D": 4}}}
    assert mod._pred_counts(confusion) == {"A": 2, "B": 4, "D": 4}


def test_stage9905_load_execution_falls_back_to_wrapper_audit(tmp_path: Path):
    mod = _load()
    mod.EXECUTION = tmp_path / "execution_result.json"
    mod.WRAPPER_AUDIT = tmp_path / "wrapper_audit.json"
    mod.BEST_STATE = tmp_path / "best_state.json"
    mod.WRAPPER_AUDIT.write_text(
        '{"runtime_executed": true, "required_row_artifacts_present": true, "eval": {"eval": {"field_exact": {"edit_localization": {"exact": 0.25}}}}}',
        encoding="utf-8",
    )
    mod.BEST_STATE.write_text('{"selected_step": 7}', encoding="utf-8")
    execution = mod._load_execution_with_fallback()
    assert execution["runtime_executed"] is True
    assert execution["required_artifacts_written"] is True
    assert execution["best_state_selection"]["selected_step"] == 7
