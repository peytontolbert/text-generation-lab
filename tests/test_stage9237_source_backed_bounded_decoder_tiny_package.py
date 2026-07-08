from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9237_source_backed_bounded_decoder_tiny_package.py"
    spec = importlib.util.spec_from_file_location("stage9237", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _source_rows():
    rows = []
    for split in ["train", "eval", "strict"]:
        for idx in range(80):
            text = f"For python, use bounded source-backed argument {split}-{idx} for a localized maintainer step."
            rows.append(
                {
                    "split": split,
                    "target_ref": f"ref-{split}-{idx}",
                    "decoder_text": text,
                    "decoder_text_sha256": f"hash-{split}-{idx}",
                    "decoder_token_len": len(text),
                    "language": "python",
                    "context_group": "callsite_plan",
                    "bounded_argument_type": "ARG_NAME",
                    "quality": {"decoder_budget_ok": True},
                }
            )
    return rows


def test_build_rows_selects_exact_caps_and_decoder_loss_only():
    mod = _load()
    rows, _selection = mod.build_rows(_source_rows())
    audit = mod.audit_rows(rows, {"source_split_counts": {}, "selected_counts": {}})
    assert len(rows) == 64
    assert audit["split_counts"] == {"eval": 16, "strict_eval": 16, "train": 32}
    assert audit["loss_counts"] == {"decoder_ce": 64}
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0


def test_audit_rejects_cross_split_duplicate_target_hashes():
    mod = _load()
    rows, _selection = mod.build_rows(_source_rows())
    rows[40]["target"]["target_text_sha256"] = rows[0]["target"]["target_text_sha256"]
    audit = mod.audit_rows(rows, {"source_split_counts": {}, "selected_counts": {}})
    assert audit["checks"]["cross_split_duplicate_target_hashes_zero"] is False
    assert "cross_split_duplicate_target_hashes_zero" in audit["failures"]


def test_audit_rejects_target_text_copied_to_input():
    mod = _load()
    rows, _selection = mod.build_rows(_source_rows())
    rows[0]["input_state"]["copied"] = rows[0]["target"]["decoder_text"]
    audit = mod.audit_rows(rows, {"source_split_counts": {}, "selected_counts": {}})
    assert audit["checks"]["target_text_copied_to_input_rows_zero"] is False
    assert "target_text_copied_to_input_rows_zero" in audit["failures"]
