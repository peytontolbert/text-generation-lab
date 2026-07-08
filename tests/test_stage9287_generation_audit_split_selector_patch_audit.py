from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9287_generation_audit_split_selector_patch_audit.py"
    spec = importlib.util.spec_from_file_location("stage9287", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9287_audits_generation_split_selector_patch():
    mod = _load()
    audit = mod.audit_patch()
    assert audit["passed"] is True
    assert audit["checks"]["cli_flag_present"] is True
    assert audit["checks"]["default_eval_strict_preserved"] is True
    assert audit["checks"]["train_split_can_be_selected"] is True
    assert all(value is False for value in audit["authority"].values())


def test_generation_audit_rows_helper_source_preserves_default_and_train_option():
    root = Path(__file__).resolve().parents[1]
    source = (root / "legacy_src/agentkernel_lite/training_loop.py").read_text(encoding="utf-8")
    assert "def _generation_audit_rows" in source
    assert "generation_audit_splits: str = \"eval,strict_eval\"" in source
    assert "generation_audit_splits or \"eval,strict_eval\"" in source
    assert '"train": train_rows' in source
    assert '"eval": eval_rows' in source
    assert '"strict_eval": strict_rows' in source
