from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9274_prefix_copy_denoise_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9274", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9274_builds_prefix_copy_rows_without_target_suffix_leak():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.audit_rows(rows, {"passed": True})
    assert audit["passed"] is True
    assert audit["rows"] == 21
    assert audit["split_counts"] == {"train": 8, "eval": 7, "strict_eval": 6}
    assert audit["approved_prefix_visible_rows"] == 21
    assert audit["full_target_visible_rows"] == 0
    assert audit["suffix_visible_rows"] == 0
    assert audit["prefix_not_target_prefix_rows"] == 0
    assert audit["excessive_prefix_rows"] == 0
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0
    assert all(row["loss_mask"] == {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False} for row in rows)
    assert all(row["model_input"]["target_grounding_mode"] == "prefix_copy_v1" for row in rows)
    assert all(row["target"]["decoder_text"].startswith(row["model_input"]["copy_prefix_span"]) for row in rows)


def test_stage9274_audit_rejects_full_target_visible_long_prefix_or_open_authority():
    mod = _load()
    rows = mod.build_rows()
    rows[0]["model_input"]["bad_copy"] = rows[0]["target"]["decoder_text"]
    rows[1]["input_state"]["approved_prefix_span"] = rows[1]["target"]["decoder_text"]
    rows[2]["authority"]["runtime_authorized"] = True
    rows[3]["loss_mask"]["decoder_ce"] = True
    audit = mod.audit_rows(rows, {"passed": True})
    assert audit["passed"] is False
    assert "full_target_visible_rows_nonzero" in audit["failures"]
    assert "excessive_prefix_rows_nonzero" in audit["failures"]
    assert "authority_rows_nonzero" in audit["failures"]
    assert "unsafe_loss_rows_nonzero" in audit["failures"]
