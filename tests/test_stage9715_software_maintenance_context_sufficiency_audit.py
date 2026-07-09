from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9715_software_maintenance_context_sufficiency_audit.py"
    spec = importlib.util.spec_from_file_location("stage9715", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9715_detects_toy_encoder_defaults_and_resolved_context_serialization():
    mod = _load()
    assert mod.trainer_default_max_encoder_tokens() == 2048
    assert mod.build_batch_default_max_encoder_tokens() == 2048
    assert mod.row_text_serializes_context_rows() is True


def test_stage9715_detects_long_context_roles_are_not_preserved_in_sample_pack():
    mod = _load()
    card = mod.context_pack_card(mod.LONG_CONTEXT_ROWS)
    assert card["exists"] is True
    assert card["first_context_row_count"] > 0
    assert card["context_roles_preserved"] is False
    assert card["first_context_has_role"] is False
    assert card["first_context_local_evidence_first"] is False


def test_stage9715_detects_active_symbol_binding_has_no_context_rows():
    mod = _load()
    card = mod.manifest_context_card(mod.SYMBOL_BINDING_MANIFEST)
    assert card["rows"] == 32
    assert card["model_input_rows"] == 32
    assert card["context_rows_present"] == 0
    assert card["has_test_coverage_nodes"] is True
    assert card["has_raw_context_rows"] is False
