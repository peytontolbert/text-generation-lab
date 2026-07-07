from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9149_metadata_only_inventory_runner_dry_run import (  # noqa: E402
    build_dry_run,
    validate_dry_run,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402
from scripts.metadata_only_path_inventory import inventory_paths, path_allowed  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def registry(latest: int = 9148) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_metadata_inventory_classifies_paths_without_reading_content() -> None:
    rows = inventory_paths(
        [
            Path("runs/local/artifacts/stage1/objective_rows.jsonl"),
            Path("runs/local/artifacts/stage1/judged_rows.jsonl"),
            Path("runs/local/artifacts/stage1/source_lineage_card.json"),
            Path("/arxiv/datasets/objective_rows.jsonl"),
        ],
        repo_root=ROOT,
    )

    assert rows
    assert any(row["candidate_type"] == "objective_rows_jsonl" for row in rows)
    assert any(row["candidate_type"] == "judge_rows_jsonl" for row in rows)
    assert any(row["candidate_type"] == "source_lineage_card_json" for row in rows)
    assert all(row["content_read"] is False for row in rows)
    assert all(row["row_count_read"] is False for row in rows)
    assert any("/arxiv/" in str(row["path"]) and row["path_allowed"] is False for row in rows)


def test_metadata_inventory_path_allowed_blocks_forbidden_roots() -> None:
    assert path_allowed(ROOT / "runs/local/artifacts/stage1/objective_rows.jsonl", ROOT) is True
    assert path_allowed(ROOT / "runs/summaries/stage1.json", ROOT) is True
    assert path_allowed(Path("/arxiv/datasets/objective_rows.jsonl"), ROOT) is False
    assert path_allowed(Path("/data/objective_rows.jsonl"), ROOT) is False
    assert path_allowed(Path("/tmp/objective_rows.jsonl"), ROOT) is False


def test_stage9149_dry_run_passes_on_synthetic_paths_only() -> None:
    card = build_dry_run(registry())

    assert validate_dry_run(card, registry()) == []
    assert all(card["checks"].values())
    assert card["metrics"]["runner_implemented"] is True
    assert card["metrics"]["dry_run_executed_on_synthetic_paths"] is True
    assert card["metrics"]["real_inventory_executed"] is False
    assert card["metrics"]["path_inventory_materialized"] is False
    assert card["metrics"]["file_content_read"] is False
    assert card["metrics"]["json_parsed"] is False
    assert card["metrics"]["jsonl_rows_counted"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["arxiv_accessed"] is False
    assert card["metrics"]["ticket_instance_materialized"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["runtime_authorized_flag"] is False
    assert not any(card["authority"].values())


def test_stage9149_rejects_execution_and_bad_frontier() -> None:
    card = build_dry_run(registry())
    card["metrics"]["real_inventory_executed"] = True
    assert "real_inventory_executed" in validate_dry_run(card, registry())

    card = build_dry_run(registry())
    card["metrics"]["file_content_read"] = True
    assert "file_content_read" in validate_dry_run(card, registry())

    card = build_dry_run(registry())
    card["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_dry_run(card, registry())

    card = build_dry_run(registry())
    assert "unexpected_registry_frontier:9999" in validate_dry_run(card, registry(latest=9999))
