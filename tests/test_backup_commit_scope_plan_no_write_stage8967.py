from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8967_backup_commit_scope_plan_no_write import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_BY_PLAN,
    classify_path,
    status_paths,
    validate_plan,
)


def registry(latest: int = 8966) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8967_classifies_include_review_and_exclude_paths() -> None:
    assert classify_path("docs/example.md") == "docs"
    assert classify_path("runs/summaries/stage.json") == "runs/summaries"
    assert classify_path("scripts/build.py") == "scripts"
    assert classify_path("tests/test_build.py") == "tests"
    assert classify_path("checkpoints/model.pt") == "exclude"
    assert classify_path("random.bin") == "review"


def test_stage8967_status_path_parser_extracts_paths() -> None:
    assert status_paths("?? docs/a.md\n M scripts/x.py\n Mdocs/MODEL_STACK_SPINE.md\n") == ["docs/a.md", "scripts/x.py", "docs/MODEL_STACK_SPINE.md"]


def test_stage8967_forbids_git_write_upload_delete_and_training() -> None:
    for op in ["git_add_now", "git_commit_now", "git_push_now", "network_upload", "delete_or_cleanup", "train_or_mine"]:
        assert op in FORBIDDEN_BY_PLAN


def test_stage8967_validation_rejects_push_or_training_reopen() -> None:
    card = {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "git_add_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_upload_performed": False,
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
    assert validate_plan(card, registry()) == []
    bad = {**card, "metrics": {**card["metrics"], "git_push_performed": True}}
    assert "git_push_performed" in validate_plan(bad, registry())
    bad_train = {**card, "metrics": {**card["metrics"], "training_authorized": True}}
    assert "training_authorized" in validate_plan(bad_train, registry())
    assert "unexpected_registry_frontier:9999" in validate_plan(card, registry(latest=9999))
