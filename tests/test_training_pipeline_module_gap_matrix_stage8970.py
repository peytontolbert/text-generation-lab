from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8970_training_pipeline_module_gap_matrix import (  # noqa: E402
    AUTHORITY_CLOSED,
    COMPONENTS,
    KNOWN_REMAINING_BLOCKERS,
    component_status,
    validate_matrix,
)


def registry(latest: int = 8969) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_attempted": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
    }


def test_stage8970_covers_core_training_pipeline_families() -> None:
    for key in [
        "safety_and_path_control",
        "dataset_judge_ranker_compiler",
        "program_state_multimodality",
        "telemetry_interpretability_attribution",
        "trainer_runtime_contracts",
    ]:
        assert key in COMPONENTS


def test_stage8970_component_status_reports_missing_files() -> None:
    status = component_status(["scripts/definitely_missing_stage8970.py"])
    assert status["complete"] is False
    assert status["missing_files"] == ["scripts/definitely_missing_stage8970.py"]


def test_stage8970_known_blockers_keep_training_closed() -> None:
    assert "native_training_execution_authority_closed" in KNOWN_REMAINING_BLOCKERS
    assert "real_arxiv_dataset_loading_closed_until_pipeline_preflight" in KNOWN_REMAINING_BLOCKERS


def test_stage8970_validation_rejects_training_or_bad_frontier() -> None:
    assert validate_matrix(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "training_authorized": True}
    assert "training_authorized" in validate_matrix(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_matrix(base_card(), registry(9999))
