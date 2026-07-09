from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9693_locked_guarded_source_backed_multisurface_compiler_refresh.py"
    spec = importlib.util.spec_from_file_location("stage9693", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_normalize_structured_row_enables_only_expected_loss_after_compiler():
    mod = _load()
    row = {
        "row_id": "r1",
        "split": "strict",
        "corrupted_state": {"language": "cpp"},
        "clean_state": {"patch_operator": "ADD_IMPORT"},
    }
    normalized = mod.normalize_row(row, "patch_operator_selection", "patch_operator_ce")
    assert normalized["split"] == "strict_eval"
    assert normalized["language_family"] == "c_cpp"
    assert normalized["route"] == "KEEP_STRUCTURED"
    assert "patch_operator_ce" not in normalized["disable_losses"]
    assert "symbol_binding_ce" in normalized["disable_losses"]
    buckets, card = mod.compile_rows([normalized], allow_decoder=True, allow_denoise=False, allow_runtime=False, require_recovered_gates=True, locked_source_ids=set())
    assert set(buckets) == {"structured_state"}
    enabled = {key: value for key, value in buckets["structured_state"][0]["loss_mask"].items() if value}
    assert enabled == {"patch_operator_ce": True}
    assert card["gate_rejected_rows"] == 0


def test_audit_compiled_rejects_loss_mismatch():
    mod = _load()
    prepared = [{"row_id": "r", "expected_enabled_loss": "symbol_binding_ce", "authority": {}}]
    audit = mod.audit_compiled(prepared, {"loss_counts": {"edit_localization_ce": 1}, "gate_rejected_rows": 0, "locked_source_exclusion_rows": 0, "route_counts": {}})
    assert audit["passed"] is False
    assert "loss_counts_do_not_match_expected_single_surface_masks" in audit["failures"]
