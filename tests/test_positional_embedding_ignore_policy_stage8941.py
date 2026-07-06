from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8941_positional_embedding_ignore_policy import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_policy,
    load_rows,
    positional_rows,
    validate_policy,
)


def registry(latest: int = 8940) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_positional_source_only_row_is_isolated() -> None:
    rows = positional_rows(load_rows())
    assert len(rows) == 1
    assert rows[0]["source_artifact"] == "dense/enc_pos_embed_weight.f32.bin"
    assert rows[0]["target_key"] is None


def test_stage8941_policy_ignores_without_copy_or_architecture_mutation() -> None:
    policy = build_policy(registry())
    assert policy["checks"]["default_policy_is_ignore"] is True
    assert policy["metrics"]["positional_copy_authorized"] is False
    assert policy["metrics"]["architecture_mutation_authorized"] is False
    assert policy["metrics"]["checkpoint_write_authorized"] is False
    assert all(value is False for value in policy["authority"].values())


def test_stage8941_validation_rejects_bad_frontier_or_open_authority() -> None:
    policy = build_policy(registry())
    assert validate_policy(policy, registry()) == []
    bad_policy = build_policy(registry())
    bad_policy["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_policy(bad_policy, registry())
    assert "unexpected_registry_frontier:9999" in validate_policy(policy, registry(latest=9999))
