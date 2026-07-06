from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8972_real_data_preflight_plan_no_arxiv_access import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_IN_PREFLIGHT,
    FUTURE_PREFLIGHT_STEPS,
    PROTECTED_ROOTS,
    validate_plan,
)


def registry(latest: int = 8971) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "arxiv_access_performed": False,
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


def test_stage8972_protects_arxiv_roots() -> None:
    assert "/arxiv" in PROTECTED_ROOTS
    assert "/arxiv/datasets" in PROTECTED_ROOTS
    assert "/arxiv/repositories" in PROTECTED_ROOTS


def test_stage8972_forbids_row_source_training_and_writes() -> None:
    for item in ["read_dataset_rows", "read_repository_source_body", "write_to_arxiv", "execute_training", "start_mining"]:
        assert item in FORBIDDEN_IN_PREFLIGHT


def test_stage8972_future_steps_are_metadata_only() -> None:
    assert "inventory_dataset_files_by_name_size_extension_only" in FUTURE_PREFLIGHT_STEPS
    assert "sample_zero_rows_until_explicit_compiler_ticket" in FUTURE_PREFLIGHT_STEPS


def test_stage8972_validation_rejects_arxiv_access_or_bad_frontier() -> None:
    assert validate_plan(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "arxiv_access_performed": True}
    assert "arxiv_access_performed" in validate_plan(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_plan(base_card(), registry(9999))
