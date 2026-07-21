from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12548_non_bears_external_patch_effect_intake.py"
SPEC = importlib.util.spec_from_file_location("stage12548", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def complete_row(**updates: object) -> dict[str, object]:
    test_id = "test_" + "9" * 40
    harness = "harness_" + "a" * 40
    trace = "trace_" + "b" * 40
    identity = {"test_id_hash": test_id, "harness_digest": harness}
    row: dict[str, object] = {
        "language_family": "rust",
        "lineage": {
            "repo_id": "repo_" + "1" * 40,
            "task_id_hash": "task_" + "2" * 40,
            "before_commit": "3" * 40,
            "after_commit": "4" * 40,
        },
        "patch": {"diff": "diff --git a/src/a.rs b/src/a.rs\n--- a/src/a.rs\n+++ b/src/a.rs\n@@ -1 +1 @@\n-old\n+new\n"},
        "test_tree_before_hash": "5" * 40,
        "test_tree_after_hash": "5" * 40,
        "verifier_before": {"identity": identity, "observed": True, "status": "FAIL", "event_index": 10, "source_id_hash": trace},
        "patch_apply": {"observed": True, "status": "success", "event_index": 20, "source_id_hash": trace},
        "verifier_after": {"identity": identity, "observed": True, "status": "PASS", "event_index": 30, "source_id_hash": trace},
        "verifier_after_revert": {"identity": identity, "observed": True, "status": "FAIL", "event_index": 40, "source_id_hash": trace},
        "provenance": {"external": True, "real_repository": True, "fixture": False, "synthetic": False, "bears": False, "source_kind": "external_real_repository"},
        "environment": {"failure": False, "dependency_failure": False},
        "contamination_keys": ["task:external-real-1"],
    }
    row.update(updates)
    return row


def evaluate(row: dict[str, object], keys: set[str] | None = None, loaded: bool = True) -> dict[str, object]:
    return MODULE.evaluate_candidate(row, keys or set(), loaded, "unit_structural_external_trace")


def test_complete_structural_candidate_is_ready() -> None:
    result = evaluate(complete_row(), {"some:other-key"})
    assert result["ready"] is True
    assert result["missing_slots"] == []


def test_unrelated_hashes_cannot_replace_structural_events() -> None:
    row = complete_row()
    row.pop("verifier_before")
    row["slot_hashes"] = {slot: "f" * 40 for slot in MODULE.REQUIRED_SLOTS}
    result = evaluate(row)
    assert result["ready"] is False
    assert {"identical_immutable_verifier", "observed_before_fail", "chronological_same_source_linkage"} <= set(result["missing_slots"])


def test_verifier_identity_must_match_structurally() -> None:
    row = complete_row()
    row["verifier_after"] = dict(row["verifier_after"], identity={"test_id_hash": "test_" + "8" * 40, "harness_digest": "harness_" + "a" * 40})
    assert "identical_immutable_verifier" in evaluate(row)["missing_slots"]


def test_order_and_same_source_are_both_required() -> None:
    row = complete_row()
    row["patch_apply"] = dict(row["patch_apply"], event_index=35, source_id_hash="trace_" + "c" * 40)
    assert "chronological_same_source_linkage" in evaluate(row)["missing_slots"]


def test_changed_test_diff_is_rejected() -> None:
    row = complete_row(patch={"diff": "diff --git a/tests/a.rs b/tests/a.rs\n--- a/tests/a.rs\n+++ b/tests/a.rs\n@@ -1 +1 @@\n-old\n+new\n"})
    assert "patch_does_not_modify_tests" in evaluate(row)["missing_slots"]


def test_revert_to_failure_is_required() -> None:
    row = complete_row()
    row.pop("verifier_after_revert")
    assert {"revert_restores_failure", "identical_immutable_verifier", "chronological_same_source_linkage"} <= set(evaluate(row)["missing_slots"])


def test_source_provenance_is_allowlisted() -> None:
    result = MODULE.evaluate_candidate(complete_row(), set(), True, "untrusted_projection")
    assert "source_adapter_positive_provenance" in result["missing_slots"]


def test_actual_contamination_intersection_blocks() -> None:
    result = evaluate(complete_row(), {"task:external-real-1"})
    assert result["contamination_manifest_intersection"] == ["task:external-real-1"]
    assert "contamination_manifest_clear" in result["missing_slots"]


def test_missing_locked_manifest_fails_closed() -> None:
    assert "contamination_manifest_clear" in evaluate(complete_row(), loaded=False)["missing_slots"]


def test_canonical_root_dedupe_does_not_join_rows() -> None:
    incomplete_a = complete_row()
    incomplete_a.pop("verifier_after")
    incomplete_b = complete_row()
    incomplete_b.pop("verifier_before")
    result = MODULE.build_intake({"a": [incomplete_a], "b": [incomplete_b]}, set())
    assert result["ready"] == []
    assert len(result["blocked"]) == 1
    assert result["blocked"][0]["canonical_root_materialization_count"] == 2


def test_duplicate_complete_roots_emit_one_intake_only_candidate() -> None:
    rows = {"unit_structural_external_trace": [complete_row(), complete_row()]}
    result = MODULE.build_intake(rows, set())
    assert len(result["ready"]) == 1
    assert result["ready"][0]["canonical_root_materialization_count"] == 2
    assert result["ready"][0]["replay_intake_only"] is True
    assert result["ready"][0]["training_allowed"] is False
    assert result["ready"][0]["admission_allowed"] is False
    assert result["ready"][0]["root_credit"] == 0



def test_task_field_aliases_intersect() -> None:
    row = complete_row(contamination_keys=["task:external-real-1"])
    result = evaluate(row, {"task_id:external-real-1"})
    assert "task:external-real-1" in result["contamination_manifest_intersection"]
    assert "contamination_manifest_clear" in result["missing_slots"]


def test_repo_url_and_owner_double_underscore_intersect() -> None:
    row = complete_row()
    row["lineage"] = dict(row["lineage"], repo_id="owner__project")
    result = evaluate(row, {"repo_id:https://github.com/Owner/Project.git"})
    assert "repo:owner/project" in result["contamination_manifest_intersection"]
    assert "contamination_manifest_clear" in result["missing_slots"]
