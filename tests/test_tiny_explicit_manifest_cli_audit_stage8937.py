from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8937_tiny_explicit_manifest_cli_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_audit,
    cli_command,
    tiny_rows,
    validate_audit,
)


def registry(latest: int = 8936) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_tiny_rows_are_closed_authority_and_cover_obligations() -> None:
    rows = tiny_rows()
    assert len(rows) == 3
    assert {row["obligation_type"] for row in rows} == {"POSITIVE_ORIGINAL", "EVIDENCE_REMOVED_OR_RETRIEVE", "CONTRASTIVE_BOUNDARY_SIBLING"}
    assert all(not any(row["authority"].values()) for row in rows)


def test_cli_command_is_no_mining_and_no_execution() -> None:
    command = cli_command()
    assert "--no-mining" in command
    assert "--no-model-execution" in command
    assert "--no-decoder-ce" in command
    assert "--no-denoise-ce" in command
    assert "--no-runtime" in command
    assert "--train" not in command


def test_stage8937_build_audit_runs_tiny_no_mining_cli_path() -> None:
    audit = build_audit(registry())
    assert audit["checks"]["manifest_path_validator_passed"] is True
    assert audit["checks"]["cli_returncode_zero"] is True
    assert audit["checks"]["cli_rows_three"] is True
    assert audit["checks"]["cli_decoder_loss_closed"] is True
    assert audit["checks"]["cli_denoise_loss_closed"] is True
    assert audit["checks"]["cli_runtime_loss_closed"] is True


def test_stage8937_validation_rejects_bad_frontier_or_open_authority() -> None:
    audit = build_audit(registry())
    assert validate_audit(audit, registry()) == []
    bad_audit = build_audit(registry())
    bad_audit["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(bad_audit, registry())
    assert "unexpected_registry_frontier:9999" in validate_audit(audit, registry(latest=9999))
