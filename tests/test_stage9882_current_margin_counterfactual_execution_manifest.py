from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9882_current_margin_counterfactual_execution_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9882", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9882_builds_trainer_compatible_current_margin_execution_manifest():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.build_audit(rows)
    assert audit["passed"] is True
    assert audit["rows"] == 48
    assert audit["split_counts"] == {"eval": 16, "strict_eval": 16, "train": 16}
    assert audit["kept_obligations"] == {
        "MIXED_REPLAY": 16,
        "POSITIVE_ORIGINAL": 16,
        "POSITIVE_ORIGINAL_EVAL_REPLAY": 16,
    }
    assert audit["dropped_obligations"] == {
        "CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN": 16,
        "EVIDENCE_REMOVED": 16,
    }


def test_stage9882_every_language_split_bucket_keeps_four_labels():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.build_audit(rows)
    for lang in ["python", "rust", "c_cpp", "web_js_ts_html"]:
        for split in ["train", "eval", "strict_eval"]:
            card = audit["bucket_cards"][f"{lang}:{split}"]
            assert card["rows"] == 4
            assert card["label_count"] == 4
            assert card["safe_signature_unique_count"] == 4
            assert card["surface_separates_labels"] is True
