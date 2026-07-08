from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9248_bounded_decoder_target_semantic_diversity_audit.py"
    spec = importlib.util.spec_from_file_location("stage9248", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _row(idx: int, text: str, arg: str = "ARG_PATH", language: str = "python", split: str = "train"):
    return {
        "row_id": f"r{idx}",
        "split": split,
        "language_family": language,
        "input_state": {
            "bounded_argument_type": arg,
            "context_group": "path_plan",
        },
        "target": {"decoder_text": text},
        "authority": {},
    }


def test_diverse_targets_pass_semantic_audit():
    mod = _load()
    rows = [
        _row(0, "Return the package root path after resolving the selected module boundary.", "ARG_PATH"),
        _row(1, "Emit the adapter symbol that owns the failing conversion branch.", "ARG_NAME", "rust", "eval"),
        _row(2, "Choose the literal timeout value from the verifier expectation.", "ARG_LITERAL", "cpp", "strict_eval"),
        _row(3, "Select the dependency import needed by the wrapper entrypoint.", "ARG_IMPORT", "web_js_ts_html"),
        _row(4, "Point the call target at the checked parser method.", "ARG_CALL", "python"),
        _row(5, "Return the config path whose flag controls the runtime mode.", "ARG_PATH", "rust"),
        _row(6, "Emit the fixture name that covers the failing branch.", "ARG_NAME", "cpp"),
        _row(7, "Select the boundary value used by the regression assertion.", "ARG_LITERAL", "web_js_ts_html"),
    ]
    audit = mod.analyze_rows(rows)
    assert audit["passed"] is True
    assert audit["language_prefix_rows"] == 0
    assert audit["template_phrase_rows"] == 0


def test_template_targets_fail_semantic_audit():
    mod = _load()
    rows = [
        _row(i, f"For python, Use the verified bounded path argument selected from localized file evidence. The argument supports path step {i}.")
        for i in range(8)
    ]
    audit = mod.analyze_rows(rows)
    assert audit["passed"] is False
    assert "language_prefix_rows_zero" in audit["failures"]
    assert "target_contains_language_rows_zero" in audit["failures"]
    assert "arg_type_echo_rows_zero" in audit["failures"]
    assert "template_phrase_rate_le_0_25" in audit["failures"]
    assert "first_token_dominance_rate_le_0_50" in audit["failures"]
