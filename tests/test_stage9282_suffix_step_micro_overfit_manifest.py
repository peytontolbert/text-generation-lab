from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9282_suffix_step_micro_overfit_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9282", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9282_builds_short_suffix_step_rows_without_suffix_leak():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.audit_rows(rows, {"passed": True})
    assert audit["passed"] is True
    assert audit["rows"] == 8
    assert audit["source_failure_rows_selected"] == 8
    assert audit["split_counts"] == {"train": 5, "eval": 1, "strict_eval": 2}
    assert audit["priming_visible_rows"] == 8
    assert audit["partial_target_visible_rows"] == 0
    assert audit["suffix_visible_rows"] == 0
    assert audit["invalid_suffix_rows"] == 0
    assert audit["over_cap_rows"] == 0
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0
    for row in rows:
        target = row["target"]["decoder_text"]
        priming = row["model_input"]["bridge_priming_span"]
        suffix = target[len(priming):].strip()
        assert target.startswith(priming)
        assert suffix
        assert len(mod.words(suffix)) <= mod.MAX_SUFFIX_WORDS
        assert len(target) <= mod.MAX_PARTIAL_TARGET_CHARS
        assert row["loss_mask"] == {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False}
        assert row["anti_cheat"]["full_original_target_in_model_visible_fields"] is False
        assert row["anti_cheat"]["suffix_step_in_model_visible_fields"] is False


def test_stage9282_audit_rejects_visible_target_and_open_authority():
    mod = _load()
    rows = mod.build_rows()
    rows[0]["model_input"]["bad_copy"] = rows[0]["target"]["decoder_text"]
    rows[1]["authority"]["runtime_authorized"] = True
    rows[2]["loss_mask"]["decoder_ce"] = True
    audit = mod.audit_rows(rows, {"passed": True})
    assert audit["passed"] is False
    assert "partial_target_visible_rows_nonzero" in audit["failures"]
    assert "authority_rows_nonzero" in audit["failures"]
    assert "unsafe_loss_rows_nonzero" in audit["failures"]


def test_stage9282_suffix_step_target_keeps_only_bounded_suffix():
    mod = _load()
    target = "Select the file path associated with the localized edit target. Keep the path reference local. Extra words remain hidden."
    priming = "Select the file path associated with the localized"
    partial, suffix = mod.suffix_step_target(target, priming)
    assert partial.startswith(priming)
    assert suffix.startswith("edit target")
    assert len(mod.words(suffix)) <= mod.MAX_SUFFIX_WORDS
    assert len(partial) < len(target)
