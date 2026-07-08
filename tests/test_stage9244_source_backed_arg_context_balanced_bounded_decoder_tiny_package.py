from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9244_source_backed_arg_context_balanced_bounded_decoder_tiny_package.py"
    spec = importlib.util.spec_from_file_location("stage9244", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _source_rows():
    rows = []
    args = ["ARG_CALL", "ARG_IMPORT", "ARG_LITERAL", "ARG_NAME", "ARG_PATH"]
    contexts = ["add_import_plan", "callsite_plan", "hold_plan", "literal_plan", "name_plan", "path_plan"]
    for split in ["train", "eval", "strict"]:
        for language in ["python", "rust", "cpp", "typescript"]:
            for arg in args:
                for context in contexts:
                    text = f"For {language}, emit a bounded {arg} argument for {context} during {split}."
                    rows.append(
                        {
                            "split": split,
                            "target_ref": f"ref-{split}-{language}-{arg}-{context}",
                            "decoder_text": text,
                            "decoder_text_sha256": f"hash-{split}-{language}-{arg}-{context}",
                            "decoder_token_len": len(text),
                            "language": language,
                            "context_group": context,
                            "bounded_argument_type": arg,
                            "quality": {"decoder_budget_ok": True},
                        }
                    )
    return rows


def test_build_rows_balances_language_argument_and_context_by_split():
    mod = _load()
    rows, selection = mod.build_rows(_source_rows())
    audit = mod.audit_rows(rows, selection)
    assert audit["passed"] is True
    assert audit["split_counts"] == {"eval": 16, "strict_eval": 16, "train": 32}
    assert audit["language_counts"] == {"cpp": 16, "python": 16, "rust": 16, "web_js_ts_html": 16}
    assert max(audit["split_arg_balance_deltas"].values()) <= 1
    assert max(audit["split_context_balance_deltas"].values()) <= 1
    assert all(value >= 5 for key, value in audit["per_split_language_arg_unique"].items() if key.startswith("train:"))
    assert all(value >= 4 for key, value in audit["per_split_language_arg_unique"].items() if not key.startswith("train:"))
    assert all(value >= 6 for key, value in audit["per_split_language_context_unique"].items() if key.startswith("train:"))
    assert all(value >= 4 for key, value in audit["per_split_language_context_unique"].items() if not key.startswith("train:"))
    assert audit["loss_counts"] == {"decoder_ce": 64}


def test_audit_rejects_split_argument_skew():
    mod = _load()
    rows, selection = mod.build_rows(_source_rows())
    for row in rows:
        state = row["input_state"]
        if row["split"] == "eval":
            state["bounded_argument_type"] = "ARG_IMPORT"
        elif row["split"] == "strict_eval":
            state["bounded_argument_type"] = "ARG_LITERAL"
    audit = mod.audit_rows(rows, selection)
    assert audit["passed"] is False
    assert "split_arg_balance_delta_le_1" in audit["failures"]
    assert "eval_strict_language_cells_cover_four_arg_types" in audit["failures"]


def test_audit_rejects_context_skew():
    mod = _load()
    rows, selection = mod.build_rows(_source_rows())
    for row in rows:
        if row["split"] == "train":
            row["input_state"]["context_group"] = "callsite_plan"
    audit = mod.audit_rows(rows, selection)
    assert audit["passed"] is False
    assert "split_context_balance_delta_le_1" in audit["failures"]
    assert "train_language_cells_cover_all_context_groups" in audit["failures"]
