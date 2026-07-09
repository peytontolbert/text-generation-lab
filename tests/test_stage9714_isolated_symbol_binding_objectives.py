from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9714_isolated_symbol_binding_objectives.py"
    spec = importlib.util.spec_from_file_location("stage9714", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9714_test_binary_manifest_is_balanced_test_only():
    mod = _load()
    rows = mod.test_binary_rows(mod.load_jsonl(mod.SOURCE_MANIFEST))
    assert len(rows) == 32
    assert {mod.qkind(row) for row in rows} == {"test"}
    assert mod.label_counts(rows) == {"TEST_BINDS_VISIBLE_SYMBOL": 16, "TEST_NEEDS_RETRIEVAL": 16}
    counts = mod.split_label_counts(rows)
    for split in ["train", "eval", "strict_eval"]:
        assert set(counts[split]) == {"TEST_BINDS_VISIBLE_SYMBOL", "TEST_NEEDS_RETRIEVAL"}


def test_stage9714_retrieve_gate_manifest_collapses_all_rows_to_three_labels():
    mod = _load()
    rows = mod.retrieve_gate_rows(mod.load_jsonl(mod.SOURCE_MANIFEST))
    assert len(rows) == 92
    assert mod.label_counts(rows) == {"BIND_AVAILABLE": 39, "RETRIEVE_MORE": 36, "ABSTAIN_UNBOUND": 17}
    assert mod.grouped_baseline(rows, mod.qkind) < 0.60


def test_stage9714_loss_authority_and_label_leak_contracts():
    mod = _load()
    for rows in [
        mod.test_binary_rows(mod.load_jsonl(mod.SOURCE_MANIFEST)),
        mod.retrieve_gate_rows(mod.load_jsonl(mod.SOURCE_MANIFEST)),
    ]:
        assert mod.count_enabled_losses(rows) == Counter({"symbol_binding_ce": len(rows)})
        assert mod.authority_violations(rows) == []
        for row in rows:
            assert row["loss_mask"]["decoder_ce"] is False
            assert row["loss_mask"]["runtime_reward"] is False
            assert row["authority"]["runtime_authorized"] is False
            assert (row.get("anti_cheat") or {}).get("stage9714_target_label_in_model_input") is False
