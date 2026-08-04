from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage12564", ROOT / "scripts/build_stage12564_authoritative_protected_lineage_preflight.py"
)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def inputs():
    return {
        "sealed": M.read_jsonl(M.SEALED),
        "locked": M.read_jsonl(M.LOCKED),
        "commitment": M.read_json(M.COMMITMENT),
        "ready": M.read_jsonl(M.READY),
        "bindings": M.read_jsonl(M.BINDINGS),
        "verified_tasks": M.manifest_tasks(json.loads(M.VERIFIED.read_text(encoding="utf-8"))),
        "scope": M.read_json(M.SCOPE),
        "stage12560": M.read_json(M.STAGE12560),
        "legacy_source_hashes": {"sealed": M.file_sha256(M.SEALED), "locked": M.file_sha256(M.LOCKED)},
        "current_commitment_source_hashes": {
            name: M.file_sha256(path) for name, path in M.COMMITMENT_SOURCES.items()
        },
        "verified_manifest_sha256": M.file_sha256(M.VERIFIED),
    }


def run(values):
    return M.audit(**values)


def test_current_preflight_is_fail_closed_and_explicit_about_unresolved_roots():
    result = run(inputs())
    assert result["legacy_source_anchors_valid"] is True
    assert result["locked_pack_exact_semantics_valid"] is True
    assert result["stage12562_commitment_sources_current"] is False
    assert "stage12562_commitment_source_hash_mismatch" in result["blocking_reasons"]
    assert result["unresolved_protected_root_count"] == 25
    assert len(result["unresolved_protected_roots"]) == 25
    assert result["training_allowed"] is False
    assert result["replay_allowed"] is False
    assert result["protected_lineage_enforcement_authoritative"] is False


def test_protected_set_mutation_is_detected():
    values = inputs()
    values["scope"]["canonical_repo_overlap_count"] = 1
    result = run(values)
    assert result["stage12561_active_protected_disjointness_proven"] is False
    assert "stage12561_active_protected_disjointness_not_proven" in result["blocking_reasons"]


def test_rehashed_commitment_tampering_does_not_validate():
    values = inputs()
    payload = values["commitment"]["commitment_payload"]
    payload["source_sha256"]["ready"] = "0" * 64
    values["commitment"]["commitment_sha256"] = M.stable_hash(payload)
    result = run(values)
    assert result["stage12562_commitment_envelope_valid"] is True
    assert result["stage12562_commitment_sources_current"] is False
    assert "stage12562_commitment_source_hash_mismatch" in result["blocking_reasons"]


def test_candidate_repo_commit_overlap_blocks():
    values = inputs()
    candidate_id = values["commitment"]["commitment_payload"]["candidate_ids"][0]
    candidate = next(row for row in values["bindings"] if row.get("candidate_id") == candidate_id)
    item = candidate["task_identity"]
    values["verified_tasks"].append({
        "repo": item["canonical_repo"], "base_commit": item["base_commit"], "instance_id": "protected-overlap"
    })
    result = run(values)
    assert result["candidate_protected_repo_commit_overlap_count"] == 1
    assert "committed_candidate_repo_commit_overlap" in result["blocking_reasons"]


def test_any_locked_pack_semantic_mutation_blocks():
    for field, value in (
        ("promotion_only", False),
        ("split_role", "train"),
        ("blocked_training_reason", "changed"),
        ("thresholds", {"no_regression_required": False}),
    ):
        values = inputs()
        values["locked"][0][field] = value
        assert run(values)["locked_pack_exact_semantics_valid"] is False


def test_missing_candidate_provenance_blocks():
    values = inputs()
    candidate_id = values["commitment"]["commitment_payload"]["candidate_ids"][0]
    row = next(row for row in values["bindings"] if row.get("candidate_id") == candidate_id)
    del row["task_identity"]["canonical_repo"]
    result = run(values)
    assert result["candidate_repo_commit_provenance_complete"] is False
    assert "candidate_repo_commit_provenance_incomplete" in result["blocking_reasons"]


def test_synthetic_sha_in_legacy_root_is_not_certification():
    values = inputs()
    values["sealed"] = copy.deepcopy(values["sealed"])
    values["sealed"][0]["stage12105_root_key"] = f"sourcebot::{'a' * 40}"
    result = run(values)
    assert result["certified_legacy_root_count"] == 0
    assert result["unresolved_protected_root_count"] == 26
    assert "protected_root_set_missing_or_duplicate" in result["blocking_reasons"]
    assert result["protected_lineage_enforcement_authoritative"] is False


def test_stage12560_anchor_cannot_be_rebased_to_mutated_source():
    values = inputs()
    values["legacy_source_hashes"]["sealed"] = "f" * 64
    values["stage12560"]["source_sha256"]["sealed"] = "f" * 64
    result = run(values)
    assert result["legacy_source_anchors_valid"] is False
    assert "stage12560_legacy_source_anchor_mismatch" in result["blocking_reasons"]


def test_protected_manifest_anchor_mismatch_blocks():
    values = inputs()
    values["verified_manifest_sha256"] = "0" * 64
    result = run(values)
    assert result["active_protected_manifest_anchored"] is False
    assert "active_protected_manifest_anchor_mismatch" in result["blocking_reasons"]


def test_candidate_repo_family_overlap_blocks_across_commits():
    values = inputs()
    candidate_id = values["commitment"]["commitment_payload"]["candidate_ids"][0]
    candidate = next(row for row in values["bindings"] if row.get("candidate_id") == candidate_id)
    values["verified_tasks"].append({
        "repo": candidate["task_identity"]["canonical_repo"],
        "base_commit": "f" * 40,
        "instance_id": "protected-repo-overlap",
    })
    result = run(values)
    assert result["candidate_protected_repo_family_overlap_count"] == 1
    assert "committed_candidate_repo_family_overlap" in result["blocking_reasons"]


def test_candidate_task_key_pair_swap_blocks():
    values = inputs()
    payload = values["commitment"]["commitment_payload"]
    payload["task_keys"][0], payload["task_keys"][1] = payload["task_keys"][1], payload["task_keys"][0]
    values["commitment"]["commitment_sha256"] = M.stable_hash(payload)
    result = run(values)
    assert result["committed_candidate_selection_exact"] is False
    assert "committed_candidate_selection_not_authoritative" in result["blocking_reasons"]
