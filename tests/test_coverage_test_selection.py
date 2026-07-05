from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from coverage_test_selection import is_test_path, select_for_rows, select_tests


def repo_index() -> dict:
    return {
        "files": ["app/auth.py", "app/db.py", "tests/test_auth.py", "tests/test_db.py", "README.md"],
        "coverage_map": {"app/auth.py": ["tests/test_auth.py"], "login": ["tests/test_auth.py"]},
        "test_to_symbols": {"tests/test_auth.py": ["login", "logout"], "tests/test_db.py": ["connect"]},
    }


def test_is_test_path() -> None:
    assert is_test_path("tests/test_auth.py") is True
    assert is_test_path("app/auth.py") is False


def test_selects_from_coverage_map_and_symbol() -> None:
    row = {"row_id": "r", "repo_index": repo_index(), "changes": [{"path": "app/auth.py", "symbol": "login"}]}
    record = select_tests(row)
    assert record["test_selection_route"] == "PASS_TARGETED_TEST_SELECTION"
    assert record["selected_tests"] == ["tests/test_auth.py"]


def test_selects_by_path_stem_when_no_coverage_map() -> None:
    row = {"row_id": "r", "repo_index": {"files": ["src/cache.py", "tests/test_cache.py"]}, "changes": [{"path": "src/cache.py"}]}
    record = select_tests(row)
    assert record["selected_tests"] == ["tests/test_cache.py"]


def test_holds_no_changeset() -> None:
    record = select_tests({"row_id": "none", "repo_index": repo_index()})
    assert record["test_selection_route"] == "HOLD_NO_CHANGESET"
    assert record["coverage_gap"] is True


def test_routes_missing_candidates_to_broad_discovery() -> None:
    row = {"row_id": "r", "repo_index": {"files": ["app/auth.py"]}, "changes": [{"path": "app/auth.py", "symbol": "login"}]}
    record = select_tests(row)
    assert record["test_selection_route"] == "NEEDS_BROAD_TEST_DISCOVERY"


def test_manifest_counts_routes() -> None:
    card = select_for_rows([
        {"row_id": "ok", "repo_index": repo_index(), "changes": [{"path": "app/auth.py", "symbol": "login"}]},
        {"row_id": "gap", "repo_index": {"files": ["app/auth.py"]}, "changes": [{"path": "app/auth.py"}]},
    ])
    assert card["metrics"]["pass_rows"] == 1
    assert card["metrics"]["coverage_gap_rows"] == 1
