from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9272_target_grounded_denoise_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9272", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9272_builds_minimal_target_grounded_denoise_rows():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.audit_rows(rows, {"passed": True})
    assert audit["passed"] is True
    assert audit["rows"] == 21
    assert audit["split_counts"] == {"train": 8, "eval": 7, "strict_eval": 6}
    assert audit["full_target_visible_rows"] == 0
    assert audit["excessive_anchor_rows"] == 0
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0
    assert all(row["loss_mask"] == {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False} for row in rows)
    assert all(row["input_state"]["target_prefix_anchor_2"] for row in rows)
    assert all(row["input_state"]["target_object_kind"] != "unknown_object" for row in rows)


def test_stage9272_audit_rejects_full_target_visible_or_open_authority():
    mod = _load()
    rows = mod.build_rows()
    rows[0]["model_input"]["bad_copy"] = rows[0]["target"]["decoder_text"]
    rows[1]["authority"]["runtime_authorized"] = True
    rows[2]["loss_mask"]["decoder_ce"] = True
    audit = mod.audit_rows(rows, {"passed": True})
    assert audit["passed"] is False
    assert "full_target_visible_rows_nonzero" in audit["failures"]
    assert "authority_rows_nonzero" in audit["failures"]
    assert "unsafe_loss_rows_nonzero" in audit["failures"]
