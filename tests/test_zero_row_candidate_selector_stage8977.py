from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8977_zero_row_candidate_selector import (  # noqa: E402
    AUTHORITY_CLOSED,
    is_named_candidate,
    is_parquet_candidate,
    select_candidates,
    validate_selector,
)


def registry(latest: int = 8976) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "candidate_file_opened": False,
            "schema_or_header_read_performed": False,
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


def test_stage8977_candidate_predicates_use_metadata_only() -> None:
    assert is_named_candidate({"relative_path": "PeytonT/100m_swe_research_timeline/train.parquet", "name": "train.parquet"})
    assert is_parquet_candidate({"extension": ".parquet"})
    assert not is_parquet_candidate({"extension": ".jsonl"})


def test_stage8977_selection_caps_and_skips_jsonl() -> None:
    rows = [
        {"relative_path": "PeytonT/100m_swe_research_timeline/train.parquet", "name": "train.parquet", "extension": ".parquet", "size_bytes": 10, "is_file": True, "is_symlink": False},
        {"relative_path": "other/a.parquet", "name": "a.parquet", "extension": ".parquet", "size_bytes": 20, "is_file": True, "is_symlink": False},
        {"relative_path": "other/b.jsonl", "name": "b.jsonl", "extension": ".jsonl", "size_bytes": 30, "is_file": True, "is_symlink": False},
    ]
    selected = select_candidates(rows, named_limit=1, parquet_limit=2)
    assert len(selected) == 2
    assert all(row["metadata_only"] is True for row in selected)
    assert all(row["schema_or_header_read"] is False for row in selected)
    assert all(row["extension"] != ".jsonl" for row in selected)


def test_stage8977_validation_rejects_file_open_or_bad_frontier() -> None:
    assert validate_selector(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "candidate_file_opened": True}
    assert "candidate_file_opened" in validate_selector(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_selector(base_card(), registry(9999))
