from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8961_repo_local_manifest_inventory_no_mining import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_inventory,
    validate_inventory,
)


def registry(latest: int = 8960) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8961_inventory_is_metadata_only_and_repo_local() -> None:
    card = build_inventory(registry())
    assert card["metrics"]["inventory_rows"] > 0
    assert card["metrics"]["content_files_opened_for_row_count"] == 0
    assert card["metrics"]["arxiv_paths_scanned"] == 0
    assert card["checks"]["content_not_loaded"] is True
    assert card["checks"]["allowed_roots_only"] is True
    assert card["checks"]["arxiv_not_scanned"] is True


def test_stage8961_keeps_mining_training_and_arxiv_closed() -> None:
    card = build_inventory(registry())
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["arxiv_read_authorized_for_compiler"] is False
    assert card["metrics"]["arxiv_write_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8961_validation_rejects_authority_or_bad_frontier() -> None:
    card = build_inventory(registry())
    assert validate_inventory(card, registry()) == []
    bad = build_inventory(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_inventory(bad, registry())
    bad_mining = build_inventory(registry())
    bad_mining["metrics"]["data_mining_authorized"] = True
    assert "data_mining_authorized" in validate_inventory(bad_mining, registry())
    assert "unexpected_registry_frontier:9999" in validate_inventory(card, registry(latest=9999))
