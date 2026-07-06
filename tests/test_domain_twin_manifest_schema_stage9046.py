from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage9046_domain_twin_manifest_schema_design import (  # noqa: E402
    SCHEMA_CONTRACT,
    build_card,
    validate_card,
)


def test_stage9046_schema_records_metadata_only_manifest_families() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    assert validate_card(card) == []
    assert set(SCHEMA_CONTRACT) == {"domain_concept_manifest", "repo_twin_manifest", "paper_twin_manifest", "domain_twin_alignment_manifest"}
    for spec in SCHEMA_CONTRACT.values():
        assert {"authority", "provenance", "anti_cheat"}.issubset(set(spec["required_fields"]))
        assert spec["forbidden_fields"]
    assert card["metrics"]["real_manifest_materialized_now"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage9046_validation_rejects_body_read_or_training() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    card["metrics"]["repo_source_body_read_authorized_now"] = True
    card["authority"]["source_emission_authorized"] = True
    failures = validate_card(card)
    assert "repo_source_body_read_authorized_now" in failures
    assert "authority_open" in failures
