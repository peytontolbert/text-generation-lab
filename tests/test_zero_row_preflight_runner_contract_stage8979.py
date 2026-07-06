from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8979_zero_row_preflight_runner_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    RUNNER_INPUTS,
    RUNNER_OUTPUT_FIELDS,
    build_contract,
    build_dry_run_rows,
    selected_rows,
    validate_contract,
)


def registry(latest: int = 8978) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8979_builds_dry_run_rows_from_local_selected_metadata() -> None:
    candidates = selected_rows()
    rows = build_dry_run_rows(candidates)
    assert len(candidates) >= 6
    assert len(rows) == len(candidates)
    assert len(RUNNER_INPUTS) >= 5
    assert len(RUNNER_OUTPUT_FIELDS) >= 10
    assert all(row["probe_executed_now"] is False for row in rows)


def test_stage8979_keeps_arxiv_rows_source_bodies_and_training_closed() -> None:
    card = build_contract(registry())
    assert card["metrics"]["arxiv_files_opened_now"] == 0
    assert card["metrics"]["probe_executed_now_rows"] == 0
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["repository_source_bodies_loaded"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8979_validation_rejects_probe_execution_or_bad_frontier() -> None:
    card = build_contract(registry())
    assert validate_contract(card, registry()) == []
    bad = build_contract(registry())
    bad["metrics"]["probe_executed_now_rows"] = 1
    assert "probe_executed_now_rows" in validate_contract(bad, registry())
    bad_authority = build_contract(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_contract(card, registry(9999))
