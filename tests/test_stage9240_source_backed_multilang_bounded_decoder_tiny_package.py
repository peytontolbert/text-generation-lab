from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9240_source_backed_multilang_bounded_decoder_tiny_package.py"
    spec = importlib.util.spec_from_file_location("stage9240", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _source_rows():
    rows = []
    for split in ["train", "eval", "strict"]:
        for language in ["python", "rust", "cpp", "typescript"]:
            for idx in range(12):
                text = f"For {language}, use bounded source-backed argument {split}-{language}-{idx} for a localized maintainer step."
                rows.append(
                    {
                        "split": split,
                        "target_ref": f"ref-{split}-{language}-{idx}",
                        "decoder_text": text,
                        "decoder_text_sha256": f"hash-{split}-{language}-{idx}",
                        "decoder_token_len": len(text),
                        "language": language,
                        "context_group": "callsite_plan",
                        "bounded_argument_type": "ARG_NAME",
                        "quality": {"decoder_budget_ok": True},
                    }
                )
    return rows


def test_build_rows_is_language_balanced_by_split():
    mod = _load()
    rows, selection = mod.build_rows(_source_rows())
    audit = mod.audit_rows(rows, selection)
    assert audit["passed"] is True
    assert audit["split_counts"] == {"eval": 16, "strict_eval": 16, "train": 32}
    assert audit["language_counts"] == {"cpp": 16, "python": 16, "rust": 16, "web_js_ts_html": 16}
    assert audit["split_language_counts"]["train:python"] == 8
    assert audit["split_language_counts"]["train:rust"] == 8
    assert audit["split_language_counts"]["train:cpp"] == 8
    assert audit["split_language_counts"]["train:web_js_ts_html"] == 8
    assert audit["loss_counts"] == {"decoder_ce": 64}


def test_audit_rejects_missing_language_cell():
    mod = _load()
    rows, selection = mod.build_rows([row for row in _source_rows() if row["language"] != "typescript"])
    audit = mod.audit_rows(rows, selection)
    assert audit["passed"] is False
    assert "rows_match_caps" in audit["failures"]
    assert "split_language_counts_match_targets" in audit["failures"]
    assert "all_required_languages_present" in audit["failures"]
