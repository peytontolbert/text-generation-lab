from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8969_github_backup_push_result import (  # noqa: E402
    AUTHORITY_CLOSED,
    PR_BLOCKER,
    validate_card,
)


def registry(latest: int = 8968) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "push_completed": True,
            "network_upload_performed": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_write_authorized": False,
            "delete_or_cleanup_performed": False,
        },
    }


def test_stage8969_records_unrelated_history_pr_blocker() -> None:
    assert "no history in common" in PR_BLOCKER


def test_stage8969_validation_accepts_backup_push_but_rejects_training() -> None:
    assert validate_card(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "training_authorized": True}
    assert "training_authorized" in validate_card(bad, registry())


def test_stage8969_validation_rejects_missing_push_or_bad_frontier() -> None:
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "push_completed": False}
    assert "push_not_completed" in validate_card(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(base_card(), registry(9999))
