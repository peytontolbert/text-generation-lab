from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9277_continuation_bridge_denoise_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9277", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9277_builds_bridge_rows_without_remainder_leak():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.audit_rows(rows, {"passed": True})
    assert audit["passed"] is True
    assert audit["rows"] == 21
    assert audit["split_counts"] == {"train": 8, "eval": 7, "strict_eval": 6}
    assert audit["prefix_visible_rows"] == 21
    assert audit["bridge_visible_rows"] == 21
    assert audit["full_target_visible_rows"] == 0
    assert audit["target_remainder_visible_rows"] == 0
    assert audit["invalid_bridge_rows"] == 0
    assert audit["excessive_visible_rows"] == 0
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0
    for row in rows:
        prefix = row["model_input"]["copy_prefix_span"]
        bridge = row["model_input"]["continuation_bridge_span"]
        assert row["target"]["decoder_text"].startswith(mod.visible_target_start(row["target"]["decoder_text"], prefix, bridge))


def test_stage9277_audit_rejects_full_target_or_open_authority():
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
