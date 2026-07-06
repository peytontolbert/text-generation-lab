from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8973_arxiv_metadata_only_preflight import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    build_preflight,
    iter_dataset_file_metadata,
    iter_repository_root_metadata,
    validate_preflight,
)


def registry(latest: int = 8972) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8973_dataset_inventory_uses_metadata_only(tmp_path: Path) -> None:
    root = tmp_path / "datasets"
    nested = root / "set_a"
    nested.mkdir(parents=True)
    (nested / "train.parquet").write_text("not read", encoding="utf-8")
    rows, truncated = iter_dataset_file_metadata(root, cap=10)
    assert truncated is False
    assert len(rows) == 1
    assert rows[0]["relative_path"] == "set_a/train.parquet"
    assert rows[0]["extension"] == ".parquet"
    assert rows[0]["size_bytes"] == len("not read")


def test_stage8973_repository_inventory_lists_top_level_dirs(tmp_path: Path) -> None:
    root = tmp_path / "repositories"
    (root / "repo_a").mkdir(parents=True)
    (root / "repo_b").mkdir()
    (root / "README.md").write_text("ignored", encoding="utf-8")
    rows, truncated = iter_repository_root_metadata(root, cap=10)
    assert truncated is False
    assert [row["name"] for row in rows] == ["repo_a", "repo_b"]


def test_stage8973_forbidden_operations_include_row_source_training_and_writes() -> None:
    for item in ["open_dataset_file_body", "read_repository_source_body", "write_to_arxiv", "start_mining", "start_training"]:
        assert item in FORBIDDEN_OPERATIONS


def test_stage8973_build_preflight_keeps_authority_closed(tmp_path: Path) -> None:
    datasets = tmp_path / "datasets"
    repos = tmp_path / "repositories"
    datasets.mkdir()
    repos.mkdir()
    (datasets / "train.jsonl").write_text('{"x": 1}\n', encoding="utf-8")
    (repos / "repo_a").mkdir()
    card = build_preflight(datasets_root=datasets, repositories_root=repos, registry=registry())
    assert card["metrics"]["dataset_inventory_rows"] == 1
    assert card["metrics"]["repository_inventory_rows"] == 1
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["repository_source_bodies_loaded"] is False
    assert validate_preflight(card, registry()) == []


def test_stage8973_validation_rejects_forbidden_flags() -> None:
    card = {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
    }
    assert validate_preflight(card, registry()) == []
    bad = {**card, "metrics": {**card["metrics"], "dataset_rows_loaded": True}}
    assert "dataset_rows_loaded" in validate_preflight(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_preflight(card, registry(9999))
