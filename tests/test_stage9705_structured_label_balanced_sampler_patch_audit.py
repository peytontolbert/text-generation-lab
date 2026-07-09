from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9705_structured_label_balanced_sampler_patch_audit.py"
    spec = importlib.util.spec_from_file_location("stage9705", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9705_balanced_sampler_exposes_every_label():
    mod = _load()
    rows = mod.load_jsonl(mod.MANIFEST)
    exposure = mod.simulated_balanced_exposure(rows, max_steps=8, batch_size=2)
    assert exposure["train_rows"] == 32
    assert exposure["unique_train_rows_seen"] == 16
    assert exposure["missing_train_labels_in_used_batches"] == []
    assert exposure["used_label_counts"] == {
        "ABSTAIN_UNBOUND": 4,
        "BIND_CALL_TO_SYMBOL": 3,
        "BIND_IMPORT_TO_MODULE": 3,
        "BIND_TEST_TO_SYMBOL": 3,
        "RETRIEVE_MORE": 3,
    }


def test_stage9705_training_loop_contains_sampler_and_result_card():
    mod = _load()
    text = mod.TRAINING_LOOP.read_text(encoding="utf-8")
    assert "_structured_label_balanced_batch_rows" in text
    assert "structured_batch_sampler" in text
    assert "label_balanced_by_primary_field" in text
