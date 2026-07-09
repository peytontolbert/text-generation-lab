from __future__ import annotations

from pathlib import Path
import sys

import pytest

pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "legacy_src"))

from agentkernel_lite.training_loop import _clean_value, _label_vocabs  # noqa: E402


def test_source_backed_clean_value_aliases_feed_structured_heads() -> None:
    row = {
        "clean_state": {
            "binding_action": "BIND_CALL_TO_SYMBOL",
            "edit_localization_target": "TARGET_SYMBOL",
            "patch_operator": "ADD_IMPORT",
            "verifier_repair_action": "REPAIR_IMPORT",
        }
    }
    assert _clean_value(row, "symbol_binding") == "BIND_CALL_TO_SYMBOL"
    assert _clean_value(row, "edit_localization") == "TARGET_SYMBOL"
    assert _clean_value(row, "patch_operator") == "ADD_IMPORT"
    assert _clean_value(row, "verifier_repair") == "REPAIR_IMPORT"


def test_label_vocabs_include_source_backed_alias_values() -> None:
    rows = [
        {"clean_state": {"binding_action": "RETRIEVE_MORE"}},
        {"clean_state": {"binding_action": "BIND_TEST_TO_SYMBOL"}},
    ]
    vocab = _label_vocabs(rows, ["symbol_binding"])
    assert set(vocab["symbol_binding"]) == {"RETRIEVE_MORE", "BIND_TEST_TO_SYMBOL"}
