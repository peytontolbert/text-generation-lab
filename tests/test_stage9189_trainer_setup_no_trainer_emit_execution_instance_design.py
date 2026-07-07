from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9189_trainer_setup_no_trainer_emit_execution_instance_design import (  # noqa: E402
    NEGATIVE_CASES,
    build_design,
    registry,
    run_negative_cases,
    validate_design,
)


def test_stage9189_design_passes() -> None:
    design = build_design(registry())
    assert validate_design(design) == []


def test_stage9189_rejects_negative_cases() -> None:
    negatives = run_negative_cases()
    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())


def test_stage9189_keeps_execution_closed() -> None:
    design = build_design(registry())
    metrics = design["metrics"]
    assert metrics["instance_open_now"] is False
    assert metrics["outputs_emitted_now"] is False
    assert metrics["trainer_invoked_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["optimizer_created"] is False
    assert metrics["backward_called"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert not any(design["authority"].values())
