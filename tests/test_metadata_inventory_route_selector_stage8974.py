from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8974_metadata_inventory_route_selector import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_NEXT_ACTIONS,
    dataset_route,
    repository_route,
    summarize_routes,
    validate_selector,
)


def registry(latest: int = 8973) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
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


def test_stage8974_dataset_route_uses_name_and_extension_metadata() -> None:
    assert dataset_route({"relative_path": "PeytonT/100m_swe_research_timeline/train.parquet", "name": "train.parquet", "extension": ".parquet"}) == "NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE"
    assert dataset_route({"relative_path": "other/train.parquet", "name": "train.parquet", "extension": ".parquet"}) == "PARQUET_TABLE_CANDIDATE"
    assert dataset_route({"relative_path": "other/blob.bin", "name": "blob.bin", "extension": ".bin"}) == "HOLD_UNKNOWN_METADATA_ONLY"


def test_stage8974_repository_route_prioritizes_software_names() -> None:
    assert repository_route({"name": "agentkernel-seq2seq-text-lab"}) == "PRIORITY_SOFTWARE_REPOSITORY_CANDIDATE"
    assert repository_route({"name": "random-repo"}) == "REPOSITORY_ROOT_METADATA_ONLY"


def test_stage8974_summarize_routes_counts_examples_and_extensions() -> None:
    card = summarize_routes([
        {"relative_path": "a/train.parquet", "name": "train.parquet", "extension": ".parquet"},
        {"relative_path": "b/data.jsonl", "name": "data.jsonl", "extension": ".jsonl"},
    ], dataset_route)
    assert card["route_counts"]["PARQUET_TABLE_CANDIDATE"] == 1
    assert card["route_counts"]["JSONL_MANIFEST_CANDIDATE"] == 1
    assert card["extension_counts"][".parquet"] == 1


def test_stage8974_forbids_body_reads_mining_training() -> None:
    for item in ["read_dataset_rows_without_route_card_audit", "read_repository_source_body_without_source_body_ticket", "write_to_arxiv", "start_mining", "start_training"]:
        assert item in FORBIDDEN_NEXT_ACTIONS


def test_stage8974_validation_rejects_forbidden_flags_or_bad_frontier() -> None:
    assert validate_selector(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "data_mining_authorized": True}
    assert "data_mining_authorized" in validate_selector(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_selector(base_card(), registry(9999))
