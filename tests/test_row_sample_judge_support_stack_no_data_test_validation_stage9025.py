from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9025_row_sample_judge_support_stack_no_data_test_validation import (  # noqa: E402
    AUTHORITY_CLOSED,
    SUPPORT_TESTS,
    build_card,
    validate_card,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def passing_test_result() -> dict[str, object]:
    return {"command": ["python", "-m", "pytest"], "returncode": 0, "stdout_tail": ["ok"], "stderr_tail": [], "output_tail": ["ok"]}


def test_stage9025_records_support_test_suite() -> None:
    card = build_card(registry(), passing_test_result())
    assert len(SUPPORT_TESTS) == 13
    assert card["metrics"]["support_tests"] == 13
    assert card["metrics"]["support_tests_present"] == 13
    assert card["metrics"]["pytest_returncode"] == 0
    assert card["checks"]["pytest_passed"] is True


def test_stage9025_keeps_only_no_data_test_execution_open() -> None:
    card = build_card(registry(), passing_test_result())
    assert card["metrics"]["module_tests_executed_now"] is True
    assert card["metrics"]["dataset_files_opened"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["judge_executed_now"] is False
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9025_validation_rejects_test_failure_or_side_effects() -> None:
    assert validate_card(build_card(registry(), passing_test_result())) == []
    failed = build_card(registry(), {**passing_test_result(), "returncode": 1})
    assert "pytest_passed" in validate_card(failed)
    unsafe = build_card(registry(), passing_test_result())
    unsafe["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_card(unsafe)
