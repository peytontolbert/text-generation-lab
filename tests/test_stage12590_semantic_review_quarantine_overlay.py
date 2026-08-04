from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12590_semantic_review_quarantine_overlay.py"
SPEC = importlib.util.spec_from_file_location("stage12590", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def candidate_rows():
    return [
        {"resolution_record_id": identity, "classification": mod.MECHANICAL_CLASSIFICATION}
        for identity in mod.REVIEWED_IDS
    ]


def test_reviewed_partition_exactly_covers_stage12589_mechanical_candidates() -> None:
    overlay = mod.build_overlay(candidate_rows())
    assert len(overlay) == len({row["stage12589_record_id"] for row in overlay}) == 20
    assert {row["stage12589_record_id"] for row in overlay} == set(mod.REVIEWED_IDS)
    statuses = {status: sum(row["stage12590_status"] == status for row in overlay) for status in (mod.QUARANTINED, mod.SURVIVOR)}
    assert statuses == {mod.QUARANTINED: 18, mod.SURVIVOR: 2}


@pytest.mark.parametrize("failure", ["missing", "unknown", "duplicate"])
def test_unknown_missing_and_duplicate_ids_fail_closed(failure: str) -> None:
    rows = candidate_rows()
    if failure == "missing":
        rows.pop()
    elif failure == "unknown":
        rows[-1] = {"resolution_record_id": "stage12589_atom_00000000000000000000", "classification": mod.MECHANICAL_CLASSIFICATION}
    else:
        rows.append(dict(rows[0]))
    with pytest.raises(mod.GateError):
        mod.build_overlay(rows)


def test_reason_specific_quarantine_and_survivor_semantics() -> None:
    by_id = {row["stage12589_record_id"]: row for row in mod.build_overlay(candidate_rows())}
    assert all(by_id[identity]["semantic_review_reason"] == mod.HIDDEN_MUTATION_REASON for identity in mod.HIDDEN_MUTATION_IDS)
    assert all(by_id[identity]["semantic_review_reason"] == mod.DOC_REPO_WIDE_REASON for identity in mod.DOC_REPO_WIDE_IDS)
    assert all(by_id[identity]["semantic_review_reason"] == mod.SURVIVOR_REASON for identity in mod.SURVIVOR_IDS)
    assert all("COMPLETE_FILESYSTEM_MUTATION_CLOSURE" in by_id[identity]["proof_requirements"] for identity in mod.HIDDEN_MUTATION_IDS)
    assert all("NO_IMPLICIT_REPO_WIDE_PROOF" in by_id[identity]["proof_requirements"] for identity in mod.DOC_REPO_WIDE_IDS)
    assert all(by_id[identity]["further_review_only"] is True for identity in mod.SURVIVOR_IDS)


def test_all_overlay_and_contract_authority_is_false() -> None:
    values = [*mod.build_overlay(candidate_rows()), mod.downstream_contract()]
    authority_keys = (
        "level3_allowed", "admission_allowed", "training_allowed", "ranking_credit_allowed",
        "positive_stop_target_allowed",
    )
    assert all(value[key] is False for value in values for key in authority_keys)
    assert all(row["normative_policy_correctness"] == "unresolved" for row in values)
    assert all(row["training_authority"] is False for row in values[:-1])


def test_global_downstream_deny_and_concentration_contract() -> None:
    contract = mod.downstream_contract()
    assert contract["default_disposition"] == "DENY"
    assert contract["stage12589_mechanical_classification_sufficient"] is False
    assert contract["only_stage12590_status_may_be_consulted"] is True
    assert set(contract["globally_denied_authority_statuses"]) == {mod.QUARANTINED, mod.SURVIVOR}
    assert contract["survivor_status_grants_training_authority"] is False
    assert contract["concentration_blocker"]["blocker_to_scale_claims"] is True
    assert {row["dimension"]: row["concentration_percent"] for row in contract["concentration_blocker"]["dimensions"]} == {
        "source": 100, "session": 100, "repo_family": 100,
    }
    proof = contract["next_private_proof_contract"]
    assert proof["complete_filesystem_mutation_closure_required"] is True
    assert proof["verifier_must_be_last_outcome_affecting_action"] is True
    assert proof["repo_wide_verifier_proves_documentation_metadata"] is False
    assert proof["explicit_documentation_metadata_assertion_required"] is True


def test_pinned_input_hash_and_generated_artifacts() -> None:
    assert mod.STAGE12589_INPUT.is_file()
    assert __import__("hashlib").sha256(mod.STAGE12589_INPUT.read_bytes()).hexdigest() == mod.PINNED_STAGE12589_SHA256
    summary = json.loads((mod.OUT / "summary.json").read_text(encoding="utf-8"))
    overlay = list(mod.iter_jsonl(mod.OUT / "semantic_review_overlay.jsonl"))
    contract = json.loads((mod.OUT / "downstream_consumer_contract.json").read_text(encoding="utf-8"))
    assert summary["audit_overlay_record_count"] == len(overlay) == 20
    assert summary["quarantined_count"] == 18
    assert summary["semantic_review_survivor_non_admitting_count"] == 2
    mod.assert_safe_output([summary, overlay, contract])


def test_hash_mismatch_fails_before_emission(tmp_path: Path) -> None:
    changed = tmp_path / "changed.jsonl"
    changed.write_text("{}\n", encoding="utf-8")
    with pytest.raises(mod.GateError, match="stage12589_input_hash_mismatch"):
        mod.execute(stage12589_input=changed, out=tmp_path / "out", summary_path=tmp_path / "summary.json")
    assert not (tmp_path / "out").exists()


def test_safe_schema_rejects_content_and_filesystem_values() -> None:
    mod.assert_safe_output(mod.build_overlay(candidate_rows()))
    for unsafe in ({"content": "secret"}, {"value": "/private/file"}, {"command": "pytest"}):
        with pytest.raises(mod.GateError):
            mod.assert_safe_output(unsafe)
