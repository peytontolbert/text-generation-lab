from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9249_semantic_bounded_decoder_target_repair_package.py"
    spec = importlib.util.spec_from_file_location("stage9249", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _source_rows():
    rows = []
    args = ["ARG_CALL", "ARG_IMPORT", "ARG_LITERAL", "ARG_NAME", "ARG_PATH"]
    contexts = ["add_import_plan", "callsite_plan", "hold_plan", "literal_plan", "name_plan", "path_plan"]
    languages = ["python", "rust", "cpp", "web_js_ts_html"]
    splits = [("train", 32), ("eval", 16), ("strict_eval", 16)]
    i = 0
    for split, count in splits:
        for n in range(count):
            arg = args[n % len(args)]
            context = contexts[n % len(contexts)]
            language = languages[n % len(languages)]
            rows.append(
                {
                    "row_id": f"stage9244_row_{i}",
                    "split": split,
                    "language_family": language,
                    "surface": "BOUNDED_DECODER_ARGUMENT_TEXT",
                    "input_state": {"bounded_argument_type": arg, "context_group": context, "language_family": language},
                    "target": {"decoder_text": f"For {language}, Use the verified {arg.lower()} argument selected from source-backed context.", "target_text_sha256": f"old-{i}", "target_ref": f"ref-{i}"},
                    "decoder_token_len": 100,
                    "loss_mask": {"decoder_ce": True},
                    "authority": {},
                    "anti_cheat": {},
                }
            )
            i += 1
    return rows


def test_repair_rows_remove_template_and_keep_decoder_loss_only():
    mod = _load()
    rows = mod.repair_rows(_source_rows())
    audit = mod.audit_rows(rows)
    assert audit["passed"] is True
    assert audit["rows"] == 64
    assert audit["language_prefix_rows"] == 0
    assert audit["template_phrase_rows"] == 0
    assert audit["arg_echo_rows"] == 0
    assert audit["target_hash_unique_rows"] == 64
    assert audit["loss_counts"] == {"decoder_ce": 64}
    assert all(row["row_id"].startswith("stage9249") for row in rows)


def test_audit_rejects_template_regression():
    mod = _load()
    rows = mod.repair_rows(_source_rows())
    rows[0]["target"]["decoder_text"] = "For python, Use the verified call argument selected from source-backed context."
    audit = mod.audit_rows(rows)
    assert audit["passed"] is False
    assert "language_prefix_rows_zero" in audit["failures"]
    assert "template_phrase_rows_zero" in audit["failures"]
    assert "arg_echo_rows_zero" in audit["failures"]
