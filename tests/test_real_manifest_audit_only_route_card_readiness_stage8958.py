from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8958_real_manifest_audit_only_route_card_readiness import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_AUDIT_GATES,
    REQUIRED_ROUTE_CARD_FIELDS,
    REQUIRED_ROUTE_OUTPUTS,
    build_card,
    validate_card,
)


def registry(latest: int = 8957) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8958_records_route_outputs_and_route_card_fields() -> None:
    card = build_card(registry())
    for output in ["judged_rows.jsonl", "ranked_rows.jsonl", "compile_card.json", "dataset_patch_queue.jsonl", "compiler_audit_card.json"]:
        assert output in REQUIRED_ROUTE_OUTPUTS
    for field in ["row_id", "route", "risk_bucket", "loss_mask", "authority", "semantic_key"]:
        assert field in REQUIRED_ROUTE_CARD_FIELDS
    assert card["metrics"]["required_route_outputs"] >= 9
    assert card["metrics"]["required_route_card_fields"] >= 10


def test_stage8958_records_path_boundaries_and_keeps_arxiv_closed() -> None:
    card = build_card(registry())
    assert "runs/local/manifests" in card["allowed_manifest_roots"]
    assert "/arxiv" in card["forbidden_absolute_roots"]
    assert "no_arxiv_input_or_write" in REQUIRED_AUDIT_GATES
    assert card["metrics"]["arxiv_read_authorized_for_compiler"] is False
    assert card["metrics"]["arxiv_write_authorized"] is False
    assert card["metrics"]["data_mining_authorized"] is False


def test_stage8958_validation_rejects_authority_or_mining_reopen() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_card(bad, registry())
    bad_mining = build_card(registry())
    bad_mining["metrics"]["data_mining_authorized"] = True
    assert "data_mining_authorized" in validate_card(bad_mining, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
