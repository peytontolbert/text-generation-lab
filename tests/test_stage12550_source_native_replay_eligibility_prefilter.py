from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12550_source_native_replay_eligibility_prefilter.py"
SPEC = importlib.util.spec_from_file_location("stage12550", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


DATASET = "/source/shard-000.parquet"
IDENTITY = ("owner__repo-1", "trajectory-1", DATASET)
COMMIT = "a" * 40


def preflight(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "candidate-1",
        "source_adapter": "Open-SWE-Traces",
        "language_family": "go",
        "source_record_ref": {"instance_id": IDENTITY[0], "trajectory_id": IDENTITY[1], "dataset_file": IDENTITY[2]},
    }
    row.update(updates)
    return row


def source(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "source_adapter": "Open-SWE-Traces",
        "instance_id": IDENTITY[0],
        "trajectory_id": IDENTITY[1],
        "dataset_file": IDENTITY[2],
        "repo": "owner/repo",
        "language": "go",
        "base_commit": COMMIT,
        "model_patch": "diff --git a/pkg/a.go b/pkg/a.go\n--- a/pkg/a.go\n+++ b/pkg/a.go\n@@ -1 +1 @@\n-old\n+new\n",
    }
    row.update(updates)
    return row


def evidence(**updates: object) -> dict[str, object]:
    before = {"authoritative": True, "argv": ["go", "test", "./pkg"], "cwd": "/checkout", "exit_code": 1, "exit_markers": [1], "event_sha256": "1" * 64}
    after = dict(before, exit_code=0, exit_markers=[0], event_sha256="2" * 64)
    value: dict[str, object] = {
        "content_addressed": True,
        "executor_id": "unit_executor",
        "bundle_sha256": "3" * 64,
        "event_chain_sha256": "4" * 64,
        "baseline_verifier": {
            "authoritative": True,
            "preexisting_at_base": True,
            "candidate_authored": False,
            "verifier_blob_sha256": "5" * 64,
            "verifier_closure_sha256": "6" * 64,
        },
        "before": before,
        "after": after,
    }
    value.update(updates)
    return value


def evaluate(p: dict[str, object] | None = None, s: dict[str, object] | None = None, **kwargs: object) -> dict[str, object]:
    defaults = {
        "executor_evidence": evidence(),
        "protected_identities": {"Open-SWE-Traces::different-task"},
        "protected_universe_available": True,
        "checkout": {
            "exists": True,
            "commit": COMMIT,
            "commit_object_verified": True,
            "upstream_remote_verified": True,
            "repo_root": "/checkout",
            "clean_tree_sha256": "7" * 64,
        },
    }
    defaults.update(kwargs)
    return MODULE.evaluate_candidate(p or preflight(), s or source(), **defaults)


def test_structurally_complete_self_attestation_is_rejected() -> None:
    claimed = source(replay={"before": "fail", "after": "pass", "ready": True})
    result = evaluate(s=claimed, executor_evidence=None)
    assert result["disposition"] == "blocked"
    assert "content_addressed_executor_evidence_missing" in result["blocking_reasons"]


def test_metadata_go_mislabeled_c_is_rejected() -> None:
    result = evaluate(p=preflight(language_family="c"))
    assert "metadata_language_mismatch" in result["blocking_reasons"]


def test_candidate_authored_verifier_is_rejected() -> None:
    proof = evidence(baseline_verifier={
        "authoritative": True,
        "preexisting_at_base": True,
        "candidate_authored": True,
        "verifier_blob_sha256": "5" * 64,
        "verifier_closure_sha256": "6" * 64,
    })
    assert "content_addressed_executor_evidence_invalid_or_self_attested" in evaluate(executor_evidence=proof)["blocking_reasons"]


def test_missing_authoritative_base_commit_is_recovery_only() -> None:
    result = evaluate(s=source(base_commit=None))
    assert result["disposition"] == "recovery_only"
    assert "authoritative_source_base_commit_missing" in result["blocking_reasons"]


def test_shell_masking_and_multiple_exit_markers_are_rejected() -> None:
    before = {"authoritative": True, "argv": ["bash", "-lc", "go test ./pkg || true"], "cwd": "/checkout", "exit_code": 0, "exit_markers": [1, 0]}
    result = evaluate(executor_evidence=evidence(before=before))
    assert "content_addressed_executor_evidence_invalid_or_self_attested" in result["blocking_reasons"]


def test_test_config_and_inline_test_mutation_are_rejected() -> None:
    test_diff = "diff --git a/tests/a.go b/tests/a.go\n--- a/tests/a.go\n+++ b/tests/a.go\n@@ -1 +1 @@\n-old\n+new\n"
    config_diff = "diff --git a/Cargo.toml b/Cargo.toml\n--- a/Cargo.toml\n+++ b/Cargo.toml\n@@ -1 +1 @@\n-old\n+new\n"
    rust_diff = "diff --git a/src/a.rs b/src/a.rs\n--- a/src/a.rs\n+++ b/src/a.rs\n@@ -1 +1,2 @@\n old\n+#[test]\n"
    assert "test_fixture_snapshot_or_inline_test_mutation" in evaluate(s=source(model_patch=test_diff))["blocking_reasons"]
    assert "build_manifest_lockfile_or_harness_config_mutation" in evaluate(s=source(model_patch=config_diff))["blocking_reasons"]
    assert "test_fixture_snapshot_or_inline_test_mutation" in evaluate(p=preflight(language_family="rust"), s=source(model_patch=rust_diff))["blocking_reasons"]


def test_duplicate_conflicting_source_rows_are_blocked_across_shards() -> None:
    duplicate = source(model_patch=source()["model_patch"] + "\n")
    result = MODULE.build_prefilter([preflight()], [source(), duplicate])
    assert len(result["blocked"]) == 1
    assert "source_native_duplicate_conflicting_rows" in result["blocked"][0]["blocking_reasons"]


def test_missing_protected_universe_blocks_overlap_resolution() -> None:
    result = evaluate(protected_universe_available=False)
    assert "protected_open_swe_swe_rebench_universe_unavailable" in result["blocking_reasons"]
    assert result["disposition"] == "recovery_only"


def test_missing_local_checkout_is_recovery_only() -> None:
    result = evaluate(checkout={"exists": False})
    assert result["disposition"] == "recovery_only"
    assert "local_checkout_or_commit_binding_missing" in result["blocking_reasons"]


def test_static_prefilter_never_emits_replay_eligibility_from_claimed_evidence() -> None:
    result = evaluate()
    assert result["disposition"] == "recovery_only"
    assert result["blocking_reasons"] == ["stage12551_authoritative_git_resolution_required"]
    assert result["training_allowed"] is False
    assert result["admission_allowed"] is False
    assert result["root_credit"] is False



def test_recovery_gaps_do_not_hide_static_semantic_blockers() -> None:
    bad = source(
        base_commit=None,
        model_patch="diff --git a/tests/a.go b/tests/a.go\n--- a/tests/a.go\n+++ b/tests/a.go\n@@ -1 +1 @@\n-old\n+new\n",
    )
    result = MODULE.evaluate_candidate(
        preflight(),
        bad,
        executor_evidence=None,
        protected_universe_available=False,
        checkout=None,
    )
    assert result["disposition"] == "blocked"
    assert "test_fixture_snapshot_or_inline_test_mutation" in result["blocking_reasons"]
    assert "authoritative_source_base_commit_missing" in result["recovery_actions"]
    assert "content_addressed_executor_evidence_missing" in result["recovery_actions"]


def test_candidate_trajectory_test_mutation_is_rejected_even_if_model_patch_is_source_only() -> None:
    test_diff = "diff --git a/tests/new_test.go b/tests/new_test.go\n--- /dev/null\n+++ b/tests/new_test.go\n@@ -0,0 +1 @@\n+func TestNew() {}\n"
    bad = source(trajectory=[{"role": "tool", "content": test_diff}])
    result = evaluate(s=bad)
    assert "candidate_trajectory_mutates_verifier_surface" in result["blocking_reasons"]


def test_checkout_dictionary_requires_verified_commit_object_and_tree() -> None:
    result = evaluate(checkout={"exists": True, "commit": COMMIT})
    assert result["disposition"] == "recovery_only"
    assert "local_checkout_or_commit_binding_missing" in result["blocking_reasons"]



def test_recovery_record_preserves_static_language_and_path_profile() -> None:
    result = evaluate(checkout={"exists": False})
    assert result["disposition"] == "recovery_only"
    assert result["source_metadata_language"] == "go"
    assert result["preflight_language_family"] == "go"
    assert result["derived_languages"] == ["go"]
    assert result["changed_paths"] == ["pkg/a.go"]



def test_recovery_record_carries_exact_patch_repo_and_source_snapshot_binding() -> None:
    row = source(
        dataset_file_sha256="8" * 64,
        source_row_index_zero_based=17,
    )
    result = evaluate(s=row, checkout={"exists": False})
    assert result["canonical_repo"] == "owner/repo"
    assert result["model_patch_sha256"] == MODULE.hashlib.sha256(row["model_patch"].encode()).hexdigest()
    assert result["source_dataset_file_sha256"] == "8" * 64
    assert result["source_row_index_zero_based"] == 17
    assert result["source_native_identity"]["dataset_file_sha256"] == "8" * 64
    assert result["source_native_identity"]["row_index_zero_based"] == 17
