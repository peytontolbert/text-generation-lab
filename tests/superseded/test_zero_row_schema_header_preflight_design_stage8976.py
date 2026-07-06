from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8976_zero_row_schema_header_preflight_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_PREFLIGHT_ACTIONS,
    SELECTED_ROUTES,
    ZERO_ROW_ALLOWED_PROBES,
    build_design,
    extension,
    validate_design,
)


def registry(latest: int = 8975) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8976_selects_metadata_candidates_without_opening_arxiv_files() -> None:
    card = build_design(registry())
    assert card["metrics"]["selected_candidates"] >= 6
    assert set(SELECTED_ROUTES).issubset(set(card["selected_routes"]))
    assert card["metrics"]["arxiv_files_opened_now"] == 0
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["repository_source_bodies_loaded"] is False


def test_stage8976_records_zero_row_probe_policy_and_forbidden_actions() -> None:
    assert ".parquet" in ZERO_ROW_ALLOWED_PROBES
    assert "read_jsonl_first_line" in FORBIDDEN_PREFLIGHT_ACTIONS
    assert "load_dataset_rows" in FORBIDDEN_PREFLIGHT_ACTIONS
    assert extension("a/b/train.parquet") == ".parquet"


def test_stage8976_validation_rejects_execution_training_or_bad_frontier() -> None:
    card = build_design(registry())
    assert validate_design(card, registry()) == []
    bad = build_design(registry())
    bad["metrics"]["schema_probe_executed_now"] = True
    assert "schema_probe_executed_now" in validate_design(bad, registry())
    bad_authority = build_design(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_design(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_design(card, registry(9999))
