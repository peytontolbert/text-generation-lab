from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9024_row_sample_judge_support_stack_readiness import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_DIAGNOSTIC_COVERAGE,
    SUPPORT_MODULES,
    build_card,
    validate_card,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9024_indexes_recovered_support_modules() -> None:
    card = build_card(registry())
    assert len(SUPPORT_MODULES) >= 13
    assert card["metrics"]["support_modules"] == len(SUPPORT_MODULES)
    assert card["missing_scripts"] == []
    assert card["missing_tests"] == []


def test_stage9024_covers_required_diagnostics() -> None:
    card = build_card(registry())
    assert set(REQUIRED_DIAGNOSTIC_COVERAGE).issubset(card["diagnostic_coverage"])
    assert card["missing_diagnostic_coverage"] == []
    for diagnostic in REQUIRED_DIAGNOSTIC_COVERAGE:
        assert card["diagnostic_coverage"][diagnostic]


def test_stage9024_keeps_execution_data_and_training_closed() -> None:
    card = build_card(registry())
    assert card["metrics"]["module_tests_executed_now"] is False
    assert card["metrics"]["dataset_files_opened"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["judge_executed_now"] is False
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9024_validation_rejects_open_authority_or_side_effects() -> None:
    assert validate_card(build_card(registry())) == []
    opened = build_card(registry())
    opened["authority"] = dict(opened["authority"])
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_card(opened)
    unsafe = build_card(registry())
    unsafe["metrics"]["module_tests_executed_now"] = True
    assert "module_tests_executed_now" in validate_card(unsafe)
