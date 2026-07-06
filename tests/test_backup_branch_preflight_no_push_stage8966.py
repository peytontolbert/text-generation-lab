from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8966_backup_branch_preflight_no_push import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_BY_PREFLIGHT,
    parse_status_lines,
    validate_preflight,
)


def registry(latest: int = 8965) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8966_status_parser_counts_categories() -> None:
    parsed = parse_status_lines([
        "?? docs/example.md",
        " M runs/local/artifacts/reconstructed_stage_registry.json",
        "?? scripts/build_stage.py",
        "?? tests/test_stage.py",
    ])
    assert parsed["total_changed_paths"] == 4
    assert parsed["category_counts"]["docs"] == 1
    assert parsed["category_counts"]["runs/local/artifacts"] == 1
    assert parsed["category_counts"]["scripts"] == 1
    assert parsed["category_counts"]["tests"] == 1


def test_stage8966_forbidden_operations_include_push_and_upload() -> None:
    assert "git_push" in FORBIDDEN_BY_PREFLIGHT
    assert "network_upload" in FORBIDDEN_BY_PREFLIGHT
    assert "huggingface_upload" in FORBIDDEN_BY_PREFLIGHT
    assert "train_model" in FORBIDDEN_BY_PREFLIGHT
    assert "mine_data" in FORBIDDEN_BY_PREFLIGHT


def test_stage8966_validation_rejects_push_or_training_reopen() -> None:
    card = {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "git_add_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_upload_performed": False,
            "huggingface_upload_performed": False,
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
    }
    assert validate_preflight(card, registry()) == []
    bad = json_clone(card)
    bad["metrics"]["git_push_performed"] = True
    assert "git_push_performed" in validate_preflight(bad, registry())
    bad_training = json_clone(card)
    bad_training["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_preflight(bad_training, registry())
    assert "unexpected_registry_frontier:9999" in validate_preflight(card, registry(latest=9999))


def json_clone(value: dict[str, object]) -> dict[str, object]:
    import copy

    return copy.deepcopy(value)
