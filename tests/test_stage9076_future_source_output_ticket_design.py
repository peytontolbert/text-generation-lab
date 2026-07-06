from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9076_future_source_output_ticket_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_TICKET_FIELDS,
    build_contract,
    validate_contract,
)


def registry(latest: int = 9075) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9076_defines_inactive_source_output_ticket() -> None:
    card = build_contract(registry())
    template = card["ticket_template"]
    for field in REQUIRED_TICKET_FIELDS:
        assert field in template
    assert card["metrics"]["ticket_instantiated_now"] is False
    assert card["metrics"]["source_metadata_read_now"] is False
    assert card["metrics"]["route_cards_materialized_now"] is False


def test_stage9076_protects_arxiv_and_blocks_body_access() -> None:
    card = build_contract(registry())
    template = card["ticket_template"]
    assert template["arxiv_policy"]["never_delete_arxiv"] is True
    assert template["arxiv_policy"]["arxiv_read_authorized_now"] is False
    assert template["arxiv_policy"]["arxiv_write_authorized_now"] is False
    assert not any(template["body_access_policy"].values())
    assert "DELETE_ARXIV" in template["forbidden_operations"]


def test_stage9076_validation_rejects_access_or_authority() -> None:
    card = build_contract(registry())
    assert validate_contract(card, registry()) == []
    bad = build_contract(registry())
    bad["metrics"]["source_metadata_read_now"] = True
    assert "source_metadata_read_now" in validate_contract(bad, registry())
    bad_arxiv = build_contract(registry())
    bad_arxiv["ticket_template"]["arxiv_policy"]["never_delete_arxiv"] = False
    assert "missing_never_delete_arxiv" in validate_contract(bad_arxiv, registry())
    bad_authority = build_contract(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_contract(card, registry(latest=9999))
