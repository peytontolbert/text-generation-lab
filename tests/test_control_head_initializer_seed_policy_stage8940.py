from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8940_control_head_initializer_seed_policy import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_policy,
    build_policy_rows,
    load_rows,
    scoped_seed,
    validate_policy,
)


def registry(latest: int = 8939) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_policy_rows_cover_target_only_heads_with_unique_seeds() -> None:
    rows = build_policy_rows(load_rows())
    assert len(rows) == 7
    seeds = [row["scoped_seed"] for row in rows]
    assert len(seeds) == len(set(seeds))
    assert scoped_seed("retrieval_query_head.weight") == scoped_seed("retrieval_query_head.weight")
    assert all(row["initialization_authorized"] is False for row in rows)


def test_stage8940_policy_keeps_initialization_and_checkpoint_blocked() -> None:
    policy = build_policy(registry())
    assert policy["checks"]["expected_target_only_rows"] is True
    assert policy["checks"]["no_initialization_authorized"] is True
    assert policy["metrics"]["checkpoint_load_authorized"] is False
    assert policy["metrics"]["checkpoint_write_authorized"] is False
    assert all(value is False for value in policy["authority"].values())


def test_stage8940_validation_rejects_bad_frontier_or_open_authority() -> None:
    policy = build_policy(registry())
    assert validate_policy(policy, registry()) == []
    bad_policy = build_policy(registry())
    bad_policy["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_policy(bad_policy, registry())
    assert "unexpected_registry_frontier:9999" in validate_policy(policy, registry(latest=9999))
