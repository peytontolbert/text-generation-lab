from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9700_symbol_binding_repair_compiler.py"
    spec = importlib.util.spec_from_file_location("stage9700", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9700_balanced_split_rows_preserve_identity_and_caps():
    mod = _load()
    source_rows = mod.load_jsonl(mod.SOURCE_MANIFEST)
    repaired = mod.balanced_split_rows(source_rows)
    assert len(source_rows) == 64
    assert len(repaired) == 64
    assert Counter(row["row_id"] for row in source_rows) == Counter(row["row_id"] for row in repaired)
    assert Counter(row["split"] for row in repaired) == {"train": 32, "eval": 16, "strict_eval": 16}


def test_stage9700_every_label_present_in_each_split():
    mod = _load()
    repaired = mod.balanced_split_rows(mod.load_jsonl(mod.SOURCE_MANIFEST))
    counts = mod.split_label_counts(repaired)
    labels = {mod.target_label(row) for row in repaired}
    for split in ["train", "eval", "strict_eval"]:
        assert set(counts[split]) == labels
        assert all(count > 0 for count in counts[split].values())
    assert counts["eval"]["BIND_IMPORT_TO_MODULE"] == 2
    assert counts["strict_eval"]["BIND_IMPORT_TO_MODULE"] == 2


def test_stage9700_loss_and_authority_contracts_unchanged():
    mod = _load()
    repaired = mod.balanced_split_rows(mod.load_jsonl(mod.SOURCE_MANIFEST))
    assert mod.count_enabled_losses(repaired) == Counter({"symbol_binding_ce": 64})
    assert mod.authority_violations(repaired) == []
    for row in repaired:
        assert row["loss_mask"]["decoder_ce"] is False
        assert row["loss_mask"]["runtime_reward"] is False
        assert row["authority"]["runtime_authorized"] is False
        assert row["authority"]["gemma_execution_authorized_next"] is False
