from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from static_analysis_security_scanner import scan_rows, scan_text


def test_passes_safe_code() -> None:
    record = scan_text("def add(a, b):\n    return a + b\n")
    assert record["security_route"] == "PASS_STATIC_SECURITY_SCAN"


def test_blocks_eval() -> None:
    record = scan_text("result = eval(user_input)")
    assert record["security_route"] == "BLOCK_SECURITY_RISK"
    assert record["findings"][0]["rule_id"] == "python_eval_exec"


def test_blocks_shell_true() -> None:
    record = scan_text("subprocess.run(cmd, shell=True)")
    assert record["security_route"] == "BLOCK_SECURITY_RISK"


def test_holds_debug_true() -> None:
    record = scan_text("DEBUG = True")
    assert record["security_route"] == "HOLD_SECURITY_REVIEW"


def test_blocks_hardcoded_secret() -> None:
    record = scan_text("api_key = 'abcdefghijklmnopqrstuvwxyz'")
    assert record["security_route"] == "BLOCK_SECURITY_RISK"


def test_manifest_counts_routes() -> None:
    card = scan_rows([
        {"row_id": "safe", "code": "x = 1"},
        {"row_id": "review", "code": "DEBUG = True"},
        {"row_id": "block", "code": "exec(payload)"},
    ])
    assert card["metrics"]["pass_rows"] == 1
    assert card["metrics"]["review_rows"] == 1
    assert card["metrics"]["blocked_rows"] == 1
