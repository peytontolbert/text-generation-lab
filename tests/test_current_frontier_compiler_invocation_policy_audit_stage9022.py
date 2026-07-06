from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9022_current_frontier_compiler_invocation_policy_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_CURRENT_FRONTIER_FLAGS,
    build_audit,
    command_flags_allowed,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9022_rejects_decoder_denoise_runtime_flags() -> None:
    allowed, forbidden = command_flags_allowed(["--input", "--output-dir", "--allow-decoder"])
    assert allowed is False
    assert forbidden == ["--allow-decoder"]
    allowed, forbidden = command_flags_allowed(["--allow-denoise", "--allow-runtime"])
    assert allowed is False
    assert forbidden == ["--allow-denoise", "--allow-runtime"]
    assert set(FORBIDDEN_CURRENT_FRONTIER_FLAGS) == {"--allow-decoder", "--allow-denoise", "--allow-runtime"}


def test_stage9022_synthetic_compile_blocks_unsafe_losses() -> None:
    card = build_audit(registry())
    assert card["metrics"]["synthetic_rows"] == 4
    assert card["metrics"]["decoder_loss_rows_under_current_policy"] == 0
    assert card["metrics"]["denoise_loss_rows_under_current_policy"] == 0
    assert card["metrics"]["runtime_loss_rows_under_current_policy"] == 0
    assert card["synthetic_compile_card"]["loss_counts"]["decoder_ce"] == 0
    assert card["synthetic_compile_card"]["loss_counts"]["denoise_ce"] == 0


def test_stage9022_keeps_data_manifest_and_training_closed() -> None:
    card = build_audit(registry())
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["manifest_materialized_now"] is False
    assert card["metrics"]["dataset_files_opened"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9022_validation_rejects_open_authority_or_loss_leak() -> None:
    assert validate_audit(build_audit(registry())) == []
    opened = build_audit(registry())
    opened["authority"] = dict(opened["authority"])
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    unsafe = build_audit(registry())
    unsafe["metrics"]["decoder_loss_rows_under_current_policy"] = 1
    assert "decoder_loss_rows_under_current_policy" in validate_audit(unsafe)
