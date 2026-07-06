from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8968_backup_push_authorization_review_no_network import (  # noqa: E402
    ALLOWED_FUTURE_COMMAND_SEQUENCE,
    AUTHORITY_CLOSED,
    FORBIDDEN_WITHOUT_NEW_EXPLICIT_AUTHORIZATION,
    REQUIRED_EXPLICIT_USER_AUTHORIZATION,
    contains_forbidden_command,
    status_paths,
    validate_card,
)


def registry(latest: int = 8967) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "git_add_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_upload_performed": False,
            "delete_or_cleanup_performed": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_write_authorized": False,
        },
    }


def test_stage8968_requires_explicit_backup_phrases() -> None:
    assert len(REQUIRED_EXPLICIT_USER_AUTHORIZATION) >= 2
    assert any("push" in phrase for phrase in REQUIRED_EXPLICIT_USER_AUTHORIZATION)
    assert any("backup" in phrase for phrase in REQUIRED_EXPLICIT_USER_AUTHORIZATION)


def test_stage8968_future_sequence_has_no_force_or_cleanup() -> None:
    assert not contains_forbidden_command(ALLOWED_FUTURE_COMMAND_SEQUENCE)
    assert any(command.startswith("git add docs") for command in ALLOWED_FUTURE_COMMAND_SEQUENCE)
    assert any(command.startswith("git push origin recovery/") for command in ALLOWED_FUTURE_COMMAND_SEQUENCE)


def test_stage8968_forbidden_list_covers_destructive_and_external_paths() -> None:
    for item in ["git push --force", "git reset", "git clean", "include_arxiv", "include_checkpoints", "upload_to_huggingface", "train_or_mine"]:
        assert item in FORBIDDEN_WITHOUT_NEW_EXPLICIT_AUTHORIZATION


def test_stage8968_status_parser_handles_compact_modified_line() -> None:
    assert status_paths(" Mdocs/MODEL_STACK_SPINE.md\n?? docs/a.md\n") == ["docs/MODEL_STACK_SPINE.md", "docs/a.md"]


def test_stage8968_validation_rejects_writes_or_bad_frontier() -> None:
    assert validate_card(base_card(), registry()) == []
    pushed = base_card()
    pushed["metrics"] = {**pushed["metrics"], "git_push_performed": True}
    assert "git_push_performed" in validate_card(pushed, registry())
    trained = base_card()
    trained["metrics"] = {**trained["metrics"], "training_authorized": True}
    assert "training_authorized" in validate_card(trained, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(base_card(), registry(9999))
