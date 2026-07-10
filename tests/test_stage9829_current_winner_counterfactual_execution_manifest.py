from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9829_current_winner_counterfactual_execution_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9829", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9829_builds_trainer_compatible_execution_manifest():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.build_audit(rows)
    assert audit["passed"] is True
    assert audit["rows"] == 60
    assert audit["split_counts"] == {"eval": 20, "strict_eval": 20, "train": 20}
    assert audit["kept_obligations"] == {
        "MIXED_REPLAY": 20,
        "POSITIVE_ORIGINAL": 20,
        "POSITIVE_ORIGINAL_EVAL_REPLAY": 20,
    }
    assert audit["dropped_obligations"] == {
        "CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN": 20,
        "EVIDENCE_REMOVED": 20,
    }


def test_stage9829_every_language_split_bucket_keeps_five_labels():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.build_audit(rows)
    for lang in ["python", "rust", "c_cpp", "web_js_ts_html"]:
        for split in ["train", "eval", "strict_eval"]:
            card = audit["bucket_cards"][f"{lang}:{split}"]
            assert card["rows"] == 5
            assert card["label_count"] == 5
            assert card["safe_signature_unique_count"] == 5
            assert card["surface_separates_labels"] is True
