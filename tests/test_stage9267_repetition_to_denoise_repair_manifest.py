from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9267_repetition_to_denoise_repair_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9267", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9267_builds_repair_and_eos_rows_from_stage9265_failures():
    mod = _load()
    repair_rows, eos_rows = mod.build_repair_rows()
    audit = mod.audit_rows(repair_rows, eos_rows, {"passed": True, "metrics": {"quality_gate_passed": False}})
    assert audit["passed"] is True
    assert audit["repair_rows"] == 6
    assert audit["eos_calibration_rows"] == 15
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0
    assert all(row["loss_mask"]["denoise_ce"] is True for row in repair_rows + eos_rows)
    assert all(row["loss_mask"]["decoder_ce"] is False for row in repair_rows + eos_rows)


def test_stage9267_audit_rejects_open_authority_or_bad_loss_mask():
    mod = _load()
    repair_rows, eos_rows = mod.build_repair_rows()
    repair_rows[0]["authority"]["runtime_authorized"] = True
    eos_rows[0]["loss_mask"]["decoder_ce"] = True
    audit = mod.audit_rows(repair_rows, eos_rows, {"passed": True, "metrics": {"quality_gate_passed": False}})
    assert audit["passed"] is False
    assert "authority_rows_nonzero" in audit["failures"]
    assert "unsafe_loss_rows_nonzero" in audit["failures"]
