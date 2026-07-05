from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ngram_repetition_style_detectors import detect_rows, detect_text, tokenize


def test_tokenize_splits_code_symbols() -> None:
    assert tokenize("def f(x): return x")[:3] == ["def", "f", "("]


def test_passes_normal_code() -> None:
    card = detect_text("def add(a, b):\n    return a + b\n")
    assert card["style_route"] == "PASS_STYLE_PRIOR"


def test_holds_high_repetition() -> None:
    text = "foo bar foo bar foo bar foo bar foo bar"
    card = detect_text(text, high_repeat_threshold=0.1)
    assert card["style_route"] == "HOLD_REPETITION_REVIEW"
    assert "high_ngram_repetition" in card["reasons"]


def test_warns_on_indent_anomaly() -> None:
    card = detect_text("def f():\n  return 1\n")
    assert card["style_route"] == "PASS_WITH_STYLE_WARNINGS"
    assert "indent_style_anomaly" in card["reasons"]


def test_warns_on_long_line() -> None:
    card = detect_text("x = '" + "a" * 120 + "'\n")
    assert "long_lines" in card["reasons"]


def test_manifest_counts_routes() -> None:
    card = detect_rows([
        {"row_id": "ok", "code": "def add(a, b):\n    return a + b\n"},
        {"row_id": "rep", "text": "foo bar foo bar foo bar foo bar"},
        {"row_id": "warn", "code": "def f():\n  return 1\n"},
    ])
    assert card["metrics"]["pass_rows"] == 1
    assert card["metrics"]["review_rows"] == 1
    assert card["metrics"]["warning_rows"] == 1
