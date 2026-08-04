from __future__ import annotations

import copy
import inspect
import importlib.util
import json
import os
from pathlib import Path

import pytest


PATH = Path(__file__).parents[1] / "scripts/build_stage12699_private_historical_retention_materialization.py"
SPEC = importlib.util.spec_from_file_location("stage12699_tested", PATH)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(S)


S93 = S._load_stage12693()


def accepted(count: int = 1):
    return {
        "counts": {"deduplicated_candidates": count},
        "language_capacity": {"python": count},
        "age_bucket_capacity": {"historical_2_to_5_years": count},
        "summary_artifact_binding": {
            "binding_sha256": S.ACCEPTED_STAGE12693_BINDING_SHA256,
        },
    }


def reseal_pair(row, proof):
    target = row["target"]["decoder_text"]
    input_text = row["input_text"]
    provenance = row["source_provenance"]
    base_objective = proof["base_comparison_objective_family"]
    kind = S93.classify_required_language(provenance["repository_relative_path"])
    assert kind is not None
    row["language_family"] = kind.language_family
    row["objective_family"] = S93.HISTORICAL_OBJECTIVES[base_objective]
    provenance["file_role"] = kind.file_role
    provenance["target_sha256"] = S._sha(target.encode())
    proof["selection_key_sha256"] = S._source_identity(row, proof)
    row["row_id"] = "stage12693_" + S._stable([
        proof["selection_key_sha256"], provenance["target_sha256"],
    ])[:24]
    proof.update({
        "row_id": row["row_id"],
        "encoder_input_sha256": S._sha(input_text.encode()),
        "model_example_sha256": S._stable([input_text, target]),
        "semantic_example_sha256": S._stable([
            base_objective,
            S93.S88.normalized_without_whitespace(input_text),
            S93.S88.normalized_without_whitespace(target),
        ]),
        "source_window_sha256": provenance["source_window_sha256"],
        "source_file_sha256": provenance["source_file_sha256"],
        "git_blob_oid": provenance["git_blob_oid"],
        "repository_relative_path_sha256": S._sha(
            provenance["repository_relative_path"].encode(),
        ),
        "target_sha256": provenance["target_sha256"],
        "historical_age_bucket": provenance["historical_age_bucket"],
        "repository_key_sha256": provenance["repository_key_sha256"],
        "content_component_sha256": provenance["content_component_sha256"],
        "historical_parent_commit_git_oid":
            provenance["historical_parent_commit_git_oid"],
        "language_family": row["language_family"],
        "objective_family": row["objective_family"],
    })
    proof["row_sha256"] = S._stable(row)
    proof["immutable_evidence_binding_sha256"] = (
        S93.immutable_row_evidence_binding(row, proof)
    )
    S93.validate_historical_row_proof(row, proof)
    return row, proof


def source_pair(*, target: str = "fixed"):
    epoch = 1640995200
    provenance = {
        "source_stage": S93.STAGE,
        "repository_key_sha256": "c" * 64,
        "content_component_sha256": "d" * 64,
        "pinned_head_commit_git_oid": "e" * 40,
        "sampling_child_commit_git_oid": "3" * 40,
        "historical_parent_commit_git_oid": "4" * 40,
        "historical_parent_tree_git_oid": "8" * 40,
        "historical_parent_commit_object_sha256": "9" * 64,
        "source_recorded_committer_epoch": epoch,
        "source_recorded_committer_timezone": "+0000",
        "age_reference_timestamp": "2026-08-03T00:00:00Z",
        "historical_age_bucket": "historical_2_to_5_years",
        "repository_relative_path": "src/example.py",
        "git_blob_oid": "5" * 40,
        "source_file_sha256": "7" * 64,
        "source_window_sha256": "1" * 64,
        "span_start_byte": 10,
        "span_end_byte": 15,
        "parent_directory": "src",
        "parent_tree_oid": "6" * 40,
        "target_object_mode": "100644",
        "target_object_type": "blob",
        "target_object_oid": "5" * 40,
        "immediate_directory_inventory_sha256": "a" * 64,
        "target_sha256": S._sha(target.encode()),
        "file_role": "code",
        "reinsertion_contract": "verified_git_blob_byte_exact_span_v1",
        "current_head_exclusion_inventory_sha256": "b" * 64,
        "current_head_example_exclusion_sha256": "f" * 64,
        "exact_reconstruction_verified": True,
    }
    row = {
        "row_id": "",
        "split": "",
        "language_family": "python",
        "objective_family": "historical_multilingual_exact_source_span_infilling",
        "input_text": "def f(): <MASK>",
        "target": {"decoder_text": target},
        "loss_mask": {"decoder_ce": True},
        "source_provenance": provenance,
        "authority": dict(S.AUTHORITY),
    }
    proof = {
        "base_comparison_objective_family":
            "multilingual_exact_source_span_infilling",
        "material_binding_sha256": "0" * 64,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
    }
    return reseal_pair(row, proof)


def rehash_result(result, mutate):
    candidate = result["candidates"][0]
    row = candidate["proof"]["stage12693_source_row"]
    proof = candidate["proof"]["stage12693_source_proof"]
    mutate(row, proof)
    reseal_pair(row, proof)
    candidate.update({
        "row_id": S._expected_candidate_id(row, proof),
        "input_text": row["input_text"],
        "target": copy.deepcopy(row["target"]),
        "language_family": row["language_family"],
        "objective_family": row["objective_family"],
        "loss_mask": copy.deepcopy(row["loss_mask"]),
        "source_provenance": copy.deepcopy(row["source_provenance"]),
    })
    candidate["proof"]["candidate_body_sha256"] = S._candidate_body_sha256(candidate)
    result["candidate_commitment_sha256"] = S._stable(result["candidates"])
    result["source_catalog"] = [{
        "repository_key_sha256": row["source_provenance"]["repository_key_sha256"],
        "content_component_sha256": row["source_provenance"]["content_component_sha256"],
        "pinned_head_commit_git_oid": row["source_provenance"]["pinned_head_commit_git_oid"],
        "visibility_class": "private_unassigned",
    }]
    result["source_catalog_commitment_sha256"] = S._stable(result["source_catalog"])


def test_target_mutation_does_not_change_trainer_row_identity():
    row_a, proof_a = source_pair(target="one")
    row_b, proof_b = source_pair(target="two")
    result_a = S.adapt_private_rows([row_a], [proof_a], accepted())
    result_b = S.adapt_private_rows([row_b], [proof_b], accepted())
    assert result_a["candidates"][0]["row_id"] == result_b["candidates"][0]["row_id"]


def test_conflicting_targets_for_one_identity_are_quarantined():
    row_a, proof_a = source_pair(target="one")
    row_b, proof_b = source_pair(target="two")
    result = S.adapt_private_rows(
        [row_a, row_b], [proof_a, proof_b], accepted(2),
    )
    assert result["candidate_count"] == 0
    assert result["quarantines"] == {"conflicting_target_for_encoder_identity": 2}


def test_private_rows_are_unassigned_and_authority_closed():
    row, proof = source_pair()
    result = S.adapt_private_rows([row], [proof], accepted())
    candidate = result["candidates"][0]
    assert candidate["split"] == ""
    assert candidate["visibility_class"] == "private_unassigned"
    assert not any(candidate["authority"].values())
    assert result["training_eligible_rows"] == 0
    assert not any(result["authority"].values())
    assert '"strict_eval"' not in json.dumps(candidate)


@pytest.mark.parametrize("target", [
    "", " ", "placeholder", "<answer>", "<missing>", "<placeholder>",
    "[PLACEHOLDER]", "TODO", "TBD", "N/A", "Answer: TODO",
    "Answer: TBD", "Answer: placeholder",
])
def test_placeholder_targets_fail_closed(target: str):
    row, proof = source_pair(target=target)
    with pytest.raises(S.Stage12699Error, match="placeholder_or_empty_target"):
        S.adapt_private_rows([row], [proof], accepted())


def test_capacity_mismatch_fails_closed():
    row, proof = source_pair()
    with pytest.raises(S.Stage12699Error, match="accepted_capacity_count_mismatch"):
        S.adapt_private_rows([row], [proof], accepted(2))


def test_public_summary_redacts_private_rows_and_catalog():
    row, proof = source_pair()
    public = S.public_summary(S.adapt_private_rows([row], [proof], accepted()))
    assert "candidates" not in public
    assert "source_catalog" not in public
    assert "quarantine_records" not in public


def test_target_digest_mismatch_fails_closed():
    row, proof = source_pair()
    proof["target_sha256"] = "0" * 64
    with pytest.raises(S.Stage12699Error, match="source_pair_evidence_mismatch"):
        S.adapt_private_rows([row], [proof], accepted())


def test_embedded_strict_split_fails_closed():
    row, proof = source_pair()
    row["split"] = "strict_eval"
    proof["row_sha256"] = S._stable(row)
    with pytest.raises(
        S.Stage12699Error, match="embedded_source_authority_or_split_not_closed",
    ):
        S.adapt_private_rows([row], [proof], accepted())


def test_survivor_is_permutation_invariant():
    row_a, proof_a = source_pair()
    row_b, proof_b = copy.deepcopy(row_a), copy.deepcopy(proof_a)
    first = S.adapt_private_rows([row_a, row_b], [proof_a, proof_b], accepted(2))
    second = S.adapt_private_rows([row_b, row_a], [proof_b, proof_a], accepted(2))
    assert first["candidate_commitment_sha256"] == second["candidate_commitment_sha256"]
    assert first["quarantine_records"] == second["quarantine_records"]


def stat_mode(path: Path) -> int:
    return os.stat(path, follow_symlinks=False).st_mode & 0o777




def install_replay(monkeypatch, rows, proofs, *, count=None):
    rows, proofs = list(rows), list(proofs)
    accepted_value = accepted(len(rows) if count is None else count)

    def replay(_repository_root):
        return (
            copy.deepcopy(accepted_value),
            (copy.deepcopy(rows), copy.deepcopy(proofs)),
        )

    monkeypatch.setattr(S, "replay_frozen_stage12693", replay)


def run_production(tmp_path: Path, monkeypatch, *, target="fixed"):
    row, proof = source_pair(target=target)
    install_replay(monkeypatch, [row], [proof])
    return S.materialize_and_persist(tmp_path / "repository", tmp_path)


def generation_paths(tmp_path: Path):
    return [path for path in tmp_path.iterdir() if path.is_dir()]


def assert_no_complete(tmp_path: Path):
    assert not list(tmp_path.glob("stage12699_*/COMPLETE"))


def test_production_api_accepts_only_roots(tmp_path: Path):
    import inspect

    signature = inspect.signature(S.materialize_and_persist)
    assert tuple(signature.parameters) == ("repository_root", "output_root")
    row, proof = source_pair()
    with pytest.raises(TypeError):
        S.materialize_and_persist(
            tmp_path, tmp_path, rows=[row], proofs=[proof],
        )


def test_no_result_or_token_based_publication_api_exists():
    forbidden = {
        "persist_private",
        "_issue_replay_authority",
        "_issue_test_replay_authority",
        "_ISSUED_REPLAY_TOKENS",
        "_ReplayAccepted",
        "_AuthorizedResult",
    }
    assert forbidden.isdisjoint(vars(S))


def test_pure_adapter_has_no_publication_side_effect(tmp_path: Path):
    row, proof = source_pair()
    result = S.adapt_private_rows([row], [proof], accepted())
    assert result["publication_performed"] is False
    assert not list(tmp_path.iterdir())


def test_production_publication_is_complete_and_mode_restricted(
    tmp_path: Path, monkeypatch,
):
    output = run_production(tmp_path, monkeypatch)
    publication = output["private_artifact"]
    generation = tmp_path / publication["generation"]
    artifact = generation / "private_materialization.json"
    complete = generation / "COMPLETE"
    assert stat_mode(generation) == 0o700
    assert stat_mode(artifact) == 0o600
    assert stat_mode(complete) == 0o600
    assert json.loads(complete.read_text())["private_materialization_sha256"] == (
        S._sha(artifact.read_bytes())
    )
    persisted = json.loads(artifact.read_text())
    assert persisted["candidates"][0]["visibility_class"] == "private_unassigned"
    assert not any(persisted["authority"].values())


def test_production_rejects_forged_adapter_rows(
    tmp_path: Path, monkeypatch,
):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    original = S.adapt_private_rows

    def forged(rows, proofs, accepted_value):
        result = original(rows, proofs, accepted_value)
        rehash_result(
            result,
            lambda source_row, source_proof:
                source_row["target"].update(decoder_text="forged target"),
        )
        return result

    monkeypatch.setattr(S, "adapt_private_rows", forged)
    with pytest.raises(
        S.Stage12699Error, match="materialization_not_derived_from_exact_replay",
    ):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


def test_production_rejects_open_authority(tmp_path: Path, monkeypatch):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    original = S.adapt_private_rows

    def forged(rows, proofs, accepted_value):
        result = original(rows, proofs, accepted_value)
        result["authority"]["training_admitted"] = True
        return result

    monkeypatch.setattr(S, "adapt_private_rows", forged)
    with pytest.raises(S.Stage12699Error, match="result_authority_not_closed"):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


def test_production_rejects_mutated_catalog(tmp_path: Path, monkeypatch):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    original = S.adapt_private_rows

    def forged(rows, proofs, accepted_value):
        result = original(rows, proofs, accepted_value)
        result["source_catalog"][0]["visibility_class"] = "strict_eval"
        return result

    monkeypatch.setattr(S, "adapt_private_rows", forged)
    with pytest.raises(
        S.Stage12699Error,
        match="source_catalog_commitment_or_visibility_mismatch",
    ):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


@pytest.mark.parametrize("mutation", [
    lambda row, proof: row["target"].update(decoder_text="forged target"),
    lambda row, proof: proof.update(
        base_comparison_objective_family=
            "exact_pinned_immediate_directory_entry_name_completion",
    ),
    lambda row, proof: row["source_provenance"].update(
        repository_relative_path="src/example.rs",
    ),
    lambda row, proof: row.update(loss_mask={"decoder_ce": False}),
    lambda row, proof: row["source_provenance"].update(
        repository_key_sha256="1" * 64,
    ),
])
def test_fully_rehashed_adapter_mutations_cannot_publish(
    tmp_path: Path, monkeypatch, mutation,
):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    original = S.adapt_private_rows

    def forged(rows, proofs, accepted_value):
        result = original(rows, proofs, accepted_value)
        rehash_result(result, mutation)
        return result

    monkeypatch.setattr(S, "adapt_private_rows", forged)
    with pytest.raises(
        S.Stage12699Error, match="materialization_not_derived_from_exact_replay",
    ):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


def test_private_publication_rejects_symlink_root(tmp_path: Path, monkeypatch):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    with pytest.raises(S.Stage12699Error, match="private_output_root_not_canonical"):
        S.materialize_and_persist(tmp_path / "repository", link)
    assert_no_complete(real)


def test_builder_digest_mismatch_rejects(monkeypatch):
    monkeypatch.setattr(S, "STAGE12693_SHA256", "0" * 64)
    with pytest.raises(S.Stage12699Error, match="stage12693_builder_digest_mismatch"):
        S._load_stage12693()


def test_accepted_artifact_digest_mismatch_rejects(monkeypatch):
    monkeypatch.setattr(S, "ACCEPTED_SUMMARY_SHA256", "0" * 64)
    with pytest.raises(S.Stage12699Error, match="accepted_stage12693_summary_mismatch"):
        S._load_accepted_summary()


def test_stale_prior_stage12693_summary_binding_and_artifact_are_rejected(monkeypatch):
    stale_path = S.ROOT / (
        "runs/local/artifacts/stage12693_source_backed_historical_old_language_retention/"
        "capacity_summaries/stage12693_capacity_summary_950810890f94c653b920963d.json"
    )
    stale_artifact_sha256 = (
        "72d6faabbfed6aac1ebb50f44df354e777aeaa4e760854521ca9d3cad4f6e2be"
    )
    stale_binding_sha256 = (
        "950810890f94c653b920963ded0e22c194aac3166a396a2a8d1a63f6996b679d"
    )

    assert S.ACCEPTED_SUMMARY != stale_path
    assert S.ACCEPTED_SUMMARY_SHA256 != stale_artifact_sha256
    assert S.ACCEPTED_STAGE12693_BINDING_SHA256 != stale_binding_sha256

    monkeypatch.setattr(S, "ACCEPTED_SUMMARY", stale_path)
    monkeypatch.setattr(S, "ACCEPTED_SUMMARY_SHA256", stale_artifact_sha256)
    monkeypatch.setattr(
        S, "ACCEPTED_STAGE12693_BINDING_SHA256", stale_binding_sha256,
    )
    with pytest.raises(S.Stage12699Error, match="accepted_stage12693_contract_mismatch"):
        S._load_accepted_summary(stale_path)


def test_replay_summary_mismatch_rejects(tmp_path: Path, monkeypatch):
    accepted_value = accepted()
    accepted_value["other"] = "expected"

    class FakeStage:
        AUTHORITATIVE_STAGE12688_CATALOG = Path("catalog")
        globally_deduplicate_historical_rows = staticmethod(
            lambda values, repository_cap=64: ((), ()),
        )

        @staticmethod
        def run_capacity_scan(*args, **kwargs):
            return {"other": "forged"}

    monkeypatch.setattr(S, "_load_accepted_summary", lambda: accepted_value)
    monkeypatch.setattr(S, "_load_stage12693", lambda: FakeStage)
    monkeypatch.setattr(S, "_replay_kwargs", lambda stage, value: {})
    with pytest.raises(
        S.Stage12699Error, match="stage12693_exact_replay_summary_mismatch",
    ):
        S.replay_frozen_stage12693(tmp_path)


def test_replay_capture_count_mismatch_rejects(tmp_path: Path, monkeypatch):
    accepted_value = accepted()
    accepted_value["other"] = "expected"

    class FakeStage:
        AUTHORITATIVE_STAGE12688_CATALOG = Path("catalog")
        globally_deduplicate_historical_rows = staticmethod(
            lambda values, repository_cap=64: ((), ()),
        )

        @staticmethod
        def run_capacity_scan(*args, **kwargs):
            return {
                "counts": accepted_value["counts"],
                "language_capacity": accepted_value["language_capacity"],
                "age_bucket_capacity": accepted_value["age_bucket_capacity"],
                "other": "expected",
            }

    monkeypatch.setattr(S, "_load_accepted_summary", lambda: accepted_value)
    monkeypatch.setattr(S, "_load_stage12693", lambda: FakeStage)
    monkeypatch.setattr(S, "_replay_kwargs", lambda stage, value: {})
    with pytest.raises(
        S.Stage12699Error, match="stage12693_replay_capture_count_mismatch",
    ):
        S.replay_frozen_stage12693(tmp_path)


def test_generation_collision_rejects_without_complete(
    tmp_path: Path, monkeypatch,
):
    row, proof = source_pair()
    result = S.adapt_private_rows([row], [proof], accepted())
    generation_commitment = S._stable({
        "candidate_commitment_sha256": result["candidate_commitment_sha256"],
        "source_catalog_commitment_sha256":
            result["source_catalog_commitment_sha256"],
        "accepted_stage12693_binding_sha256":
            result["accepted_stage12693_binding_sha256"],
    })
    suffix = "a" * 16
    (tmp_path / f"stage12699_{generation_commitment[:24]}_{suffix}").mkdir()
    install_replay(monkeypatch, [row], [proof])
    monkeypatch.setattr(S.secrets, "token_hex", lambda size: "a" * (size * 2))
    with pytest.raises(S.Stage12699Error, match="private_generation_collision"):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


@pytest.mark.parametrize("prefix", [".materialization.tmp.", ".complete.tmp."])
def test_temporary_collisions_reject_without_complete(
    tmp_path: Path, monkeypatch, prefix,
):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    original_open = S.os.open

    def collide(path, flags, *args, **kwargs):
        if isinstance(path, str) and path.startswith(prefix):
            raise FileExistsError(path)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(S.os, "open", collide)
    with pytest.raises(S.Stage12699Error, match="private_temporary_collision"):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


def test_generation_identity_race_rejects_without_complete(
    tmp_path: Path, monkeypatch,
):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    monkeypatch.setattr(S, "_same_inode", lambda *args, **kwargs: False)
    with pytest.raises(S.Stage12699Error, match="generation_identity_changed"):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


def test_root_race_rejects_without_complete(tmp_path: Path, monkeypatch):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    original = S._revalidate_root
    calls = 0

    def race(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise S.Stage12699Error("private_output_root_identity_changed")
        return original(*args, **kwargs)

    monkeypatch.setattr(S, "_revalidate_root", race)
    with pytest.raises(
        S.Stage12699Error, match="private_output_root_identity_changed",
    ):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


@pytest.mark.parametrize("destination", [
    "private_materialization.json",
    "COMPLETE",
])
def test_rename_failures_before_commit_leave_no_complete(
    tmp_path: Path, monkeypatch, destination,
):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    original = S._rename_noreplace

    def interrupt(directory_fd, source, requested_destination):
        if requested_destination == destination:
            raise S.Stage12699Error("simulated_publication_interruption")
        return original(directory_fd, source, requested_destination)

    monkeypatch.setattr(S, "_rename_noreplace", interrupt)
    with pytest.raises(S.Stage12699Error, match="simulated_publication_interruption"):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


def test_fsync_failure_before_commit_leaves_no_complete(
    tmp_path: Path, monkeypatch,
):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    original = S.os.fsync
    calls = 0

    def fail_once(fd):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("simulated fsync failure")
        return original(fd)

    monkeypatch.setattr(S.os, "fsync", fail_once)
    with pytest.raises(OSError, match="simulated fsync failure"):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


def test_complete_rename_is_final_fallible_commit_hook(
    tmp_path: Path, monkeypatch,
):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    committed = False
    original_rename = S._rename_noreplace
    original_same_inode = S._same_inode
    original_revalidate = S._revalidate_root
    original_write = S._write_all
    original_fsync = S.os.fsync

    def assert_precommit():
        assert committed is False

    def rename(directory_fd, source, destination):
        nonlocal committed
        assert_precommit()
        original_rename(directory_fd, source, destination)
        if destination == "COMPLETE":
            committed = True

    def same_inode(*args, **kwargs):
        assert_precommit()
        return original_same_inode(*args, **kwargs)

    def revalidate(*args, **kwargs):
        assert_precommit()
        return original_revalidate(*args, **kwargs)

    def write_all(*args, **kwargs):
        assert_precommit()
        return original_write(*args, **kwargs)

    def fsync(*args, **kwargs):
        assert_precommit()
        return original_fsync(*args, **kwargs)

    monkeypatch.setattr(S, "_rename_noreplace", rename)
    monkeypatch.setattr(S, "_same_inode", same_inode)
    monkeypatch.setattr(S, "_revalidate_root", revalidate)
    monkeypatch.setattr(S, "_write_all", write_all)
    monkeypatch.setattr(S.os, "fsync", fsync)
    output = S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert committed is True
    complete = tmp_path / output["private_artifact"]["generation"] / "COMPLETE"
    assert complete.is_file()


def test_visible_complete_remains_success_when_cleanup_close_fails(
    tmp_path: Path, monkeypatch,
):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    committed = False
    original_rename = S._rename_noreplace
    original_close = S.os.close

    def rename(directory_fd, source, destination):
        nonlocal committed
        original_rename(directory_fd, source, destination)
        if destination == "COMPLETE":
            committed = True

    def close(fd):
        if committed:
            raise RuntimeError("response-side cleanup interruption")
        return original_close(fd)

    monkeypatch.setattr(S, "_rename_noreplace", rename)
    monkeypatch.setattr(S.os, "close", close)
    output = S.materialize_and_persist(tmp_path / "repository", tmp_path)
    complete = tmp_path / output["private_artifact"]["generation"] / "COMPLETE"
    assert complete.is_file()


def test_production_rejects_silently_omitted_replay_rows(
    tmp_path: Path, monkeypatch,
):
    row, proof = source_pair()
    install_replay(monkeypatch, [row], [proof])
    original = S.adapt_private_rows

    def forged(rows, proofs, accepted_value):
        result = original(rows, proofs, accepted_value)
        result["candidates"] = []
        result["candidate_count"] = 0
        result["candidate_commitment_sha256"] = S._stable([])
        result["language_counts"] = {}
        result["age_bucket_counts"] = {}
        result["source_catalog"] = []
        result["source_catalog_commitment_sha256"] = S._stable([])
        return result

    monkeypatch.setattr(S, "adapt_private_rows", forged)
    with pytest.raises(
        S.Stage12699Error, match="materialization_row_accounting_mismatch",
    ):
        S.materialize_and_persist(tmp_path / "repository", tmp_path)
    assert_no_complete(tmp_path)


def test_complete_commit_is_structurally_last_in_production_try():
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(S.materialize_and_persist)))
    function = tree.body[0]
    publication_try = next(
        statement for statement in function.body if isinstance(statement, ast.Try)
    )
    commit, response = publication_try.body[-2:]
    assert isinstance(commit, ast.Expr)
    assert isinstance(commit.value, ast.Call)
    assert isinstance(commit.value.func, ast.Name)
    assert commit.value.func.id == "_rename_noreplace"
    assert isinstance(commit.value.args[2], ast.Constant)
    assert commit.value.args[2].value == "COMPLETE"
    assert isinstance(response, ast.Return)
    assert publication_try.finalbody
    assert any(
        isinstance(node, ast.ExceptHandler)
        and isinstance(node.type, ast.Name)
        and node.type.id == "BaseException"
        for node in ast.walk(publication_try)
    )
