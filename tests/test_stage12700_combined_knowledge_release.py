from __future__ import annotations

import hashlib
import inspect
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12700_combined_knowledge_release.py"
SPEC = importlib.util.spec_from_file_location("stage12700", SCRIPT)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = S
SPEC.loader.exec_module(S)


STAGE_OBJECTIVES = {
    12687: ["python_parser_source_span_infilling"] * 3,
    12688: [
        "multilingual_exact_source_span_infilling",
        "exact_pinned_immediate_directory_entry_name_completion",
    ],
    12689: [
        "maintenance_commit_message_span_completion",
        "small_diff_exact_child_hunk_completion",
    ],
    12690: [
        "python_symbol_reference_prediction",
        "python_test_file_association",
    ],
    12691: [
        "python_api_keyword_name_completion",
        "python_sphinx_doc_code_test_relationship",
    ],
    12692: [
        "declarative_test_build_scalar_completion",
        "declarative_test_build_target_resolution",
    ],
    12698: [
        "repository_structure_classification",
        "test_layout_classification",
        "documentation_layout_classification",
        "parsed_declaration_classification",
        "compact_observed_verifier_summary",
    ],
    12699: [
        "historical_multilingual_exact_source_span_infilling",
        "historical_exact_pinned_immediate_directory_entry_name_completion",
    ],
}


def artifact(stage: int, objectives: list[str]) -> S.CORE.StageArtifacts:
    rows = []
    proofs = []
    catalog = []
    for index, objective in enumerate(objectives):
        split = {
            (12687, 0): "strict_eval",
            (12687, 1): "eval",
            (12688, 0): "strict_eval",
            (12688, 1): "eval",
        }.get((stage, index), "train")
        repo = S.stable(["repo", stage, index])
        component = S.stable(["component", stage, index])
        revision = hashlib.sha1(
            f"fixture-revision:{stage}:{index}".encode(),
        ).hexdigest()
        source = S.stable(["source", stage, index])
        row = {
            "row_id": f"r{stage}_{index}",
            "split": split,
            "objective_family": objective,
            "input_text": f"objective: {objective}\nevidence: fixture-{stage}-{index}",
            "target": {"decoder_text": f"verified_target_{stage}_{index}"},
            "source_provenance": {
                "repository_key_sha256": repo,
                "content_component_sha256": component,
                "revision": revision,
                "source_file_sha256": source,
            },
        }
        input_sha = hashlib.sha256(row["input_text"].encode()).hexdigest()
        target_sha = hashlib.sha256(row["target"]["decoder_text"].encode()).hexdigest()
        proof = {
            "row_id": row["row_id"],
            "split": split,
            "objective_family": objective,
            "repository_key_sha256": repo,
            "content_component_sha256": component,
            "revision": revision,
            "row_sha256": S.stable(row),
            "semantic_example_sha256": S.stable(["semantic", stage, index]),
            "source_window_sha256": S.stable(["window", stage, index]),
            "source_file_sha256": source,
            "candidate_evidence_sha256": S.stable(["candidate", stage, index]),
            "patch_fingerprint_sha256": S.stable(["patch", stage, index]),
        }
        if stage == 12688:
            proof["encoder_input_sha256"] = input_sha
        elif stage != 12687:
            proof["model_input_sha256"] = input_sha
        if stage in {12687, 12688}:
            proof["model_example_sha256"] = S.stable(
                [row["input_text"], row["target"]["decoder_text"]]
            )
        if stage in {12687, 12688, 12689, 12691, 12698, 12699}:
            proof["target_sha256"] = target_sha
        rows.append(row)
        proofs.append(proof)
        catalog.append({
            "repository_key_sha256": repo,
            "content_component_sha256": component,
            "revision": revision,
            "root_commit_git_oids": [revision],
            "source_file_sha256s": [source],
            "split": split,
        })
    return S.CORE.StageArtifacts(
        stage,
        S.CORE.STAGE_SCHEMAS[stage],
        tuple(rows),
        tuple(proofs),
        tuple(catalog),
        catalog_commitment_sha256=S.CORE._records_commitment(catalog),
        ledger_commitment_sha256=S.CORE._records_commitment(proofs),
    )


def all_inputs():
    return [artifact(stage, objectives) for stage, objectives in STAGE_OBJECTIVES.items()]


def authenticated_strict_refs(inputs):
    return frozenset(
        f"stage{item.stage}:{row['row_id']}"
        for item in inputs
        for row in item.rows
        if row["split"] == "strict_eval"
    )


def subset_artifact(item, predicate):
    rows = tuple(row for row in item.rows if predicate(row))
    row_ids = {row["row_id"] for row in rows}
    proofs = tuple(proof for proof in item.ledger if proof["row_id"] in row_ids)
    repo_ids = {proof["repository_key_sha256"] for proof in proofs}
    catalog = tuple(
        entry for entry in item.catalog
        if entry["repository_key_sha256"] in repo_ids
    )
    return S.CORE.StageArtifacts(
        item.stage, item.schema_version, rows, proofs, catalog,
        catalog_commitment_sha256=S.CORE._records_commitment(catalog),
        ledger_commitment_sha256=S.CORE._records_commitment(proofs),
    )


def private_candidate(stage: int, objective: str, *, target: dict | None = None):
    repo = S.stable(["private-repo", stage, objective])
    component = S.stable(["private-component", stage, objective])
    revision = f"{stage:040x}"
    target = target or {"decoder_text": "authenticated value"}
    return {
        "objective_family": objective,
        "input_text": f"private input {stage} {objective}",
        "target": target,
        "source_provenance": {
            "repository_key_sha256": repo,
            "content_component_sha256": component,
            "revision": revision,
            "source_file_sha256": S.stable(["private-file", stage, objective]),
        },
        "proof": {
            "repository_key_sha256": repo,
            "content_component_sha256": component,
            "revision": revision,
            "source_file_sha256": S.stable(["private-file", stage, objective]),
            "immutable_evidence_binding_sha256": S.stable(["binding", stage, objective]),
        },
        "authority": dict(S.AUTHORITY),
    }


def write_private_generation(root: Path, stage: int, candidates: list[dict]):
    generation = f"stage{stage}_fixture"
    directory = root / generation
    directory.mkdir(mode=0o700)
    source_catalog = []
    if stage == 12699:
        accepted = S.stable(["accepted-stage12693"])
        for candidate in candidates:
            candidate["proof"]["accepted_stage12693_binding_sha256"] = accepted
            candidate["proof"]["candidate_body_sha256"] = S._candidate_body_sha256(candidate)
            provenance = candidate["source_provenance"]
            source_catalog.append({
                "repository_key_sha256": provenance["repository_key_sha256"],
                "content_component_sha256": provenance["content_component_sha256"],
                "pinned_head_commit_git_oid": provenance["revision"],
                "visibility_class": "private_unassigned",
            })
        summary = {
            "candidate_count": len(candidates),
            "candidate_commitment_sha256": S.stable(candidates),
            "source_catalog_commitment_sha256": S.stable(source_catalog),
            "accepted_stage12693_binding_sha256": accepted,
            "training_eligible_rows": 0,
            "authority": dict(S.AUTHORITY),
        }
        generation_commitment = S.stable({
            "candidate_commitment_sha256": summary["candidate_commitment_sha256"],
            "source_catalog_commitment_sha256": summary["source_catalog_commitment_sha256"],
            "accepted_stage12693_binding_sha256": accepted,
        })
        record_type = "stage12699_private_historical_retention_bundle_v1"
    else:
        summary = {
            "candidate_count": len(candidates),
            "candidate_commitment_sha256": S.stable(candidates),
            "stage12696_package_manifest_sha256": "8" * 64,
            "stage12697_capacity_commitment_sha256": "9" * 64,
            "training_eligible_rows": 0,
            "authority": dict(S.AUTHORITY),
        }
        generation_commitment = S.stable({
            "candidate_commitment_sha256": summary["candidate_commitment_sha256"],
            "stage12696_package_manifest_sha256": "8" * 64,
            "stage12697_capacity_commitment_sha256": "9" * 64,
        })
        record_type = "stage12698_private_materialization_bundle_v1"
    bundle = {
        "record_type": record_type,
        "generation_commitment_sha256": generation_commitment,
        "summary": summary,
        "candidates": candidates,
        "source_catalog": source_catalog,
        "authority": dict(S.AUTHORITY),
    }
    payload = json.dumps(
        bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii") + b"\n"
    artifact_path = directory / "private_materialization.json"
    artifact_path.write_bytes(payload)
    artifact_path.chmod(0o600)
    marker = {
        "generation_commitment_sha256": bundle["generation_commitment_sha256"],
        "private_materialization_sha256": hashlib.sha256(payload).hexdigest(),
    }
    complete = directory / "COMPLETE"
    complete.write_text(json.dumps(marker, sort_keys=True, separators=(",", ":")) + "\n")
    complete.chmod(0o600)
    return generation, hashlib.sha256(payload).hexdigest()


def strict_artifact(stage: int) -> S.CORE.StageArtifacts:
    item = artifact(stage, [STAGE_OBJECTIVES[stage][0]])
    rows = []
    proofs = []
    for source_row, source_proof in zip(item.rows, item.ledger, strict=True):
        row = dict(source_row, split="strict_eval")
        proof = dict(source_proof, split="strict_eval", row_sha256=S.stable(row))
        rows.append(row)
        proofs.append(proof)
    catalog = [dict(entry, split="strict_eval") for entry in item.catalog]
    return S.CORE.StageArtifacts(
        stage, item.schema_version, tuple(rows), tuple(proofs), tuple(catalog),
        catalog_commitment_sha256=S.CORE._records_commitment(catalog),
        ledger_commitment_sha256=S.CORE._records_commitment(proofs),
    )


def write_strict_generation(root: Path):
    root.mkdir(mode=0o700)
    generation = "a" * 64
    directory = root / generation
    directory.mkdir(mode=0o700)
    contracts = {}
    source_entries = []
    for stage in S.STRICT_SOURCE_STAGES:
        item = strict_artifact(stage)
        records = {
            "rows": item.rows,
            "proofs": item.ledger,
            "catalog": item.catalog,
        }
        snapshot = {
            "strict_rows_sha256": S.stable(item.rows),
            "strict_proofs_sha256": S.stable(item.ledger),
            "strict_catalog_sha256": S.stable(item.catalog),
        }
        source_entries.append({
            "stage": stage,
            "strict_row_count": 1,
            "validated_snapshot_contract": snapshot,
            "validated_snapshot_commitment_sha256": S.stable(snapshot),
        })
        for kind, values in records.items():
            name = f"stage{stage}_strict_{kind}.jsonl"
            payload = S._payload(values)
            path = directory / name
            path.write_bytes(payload)
            path.chmod(0o600)
            contracts[name] = {
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
    manifest = {
        "stage": "stage12701_confidential_strict_knowledge_materialization",
        "schema_version": 1,
        "generation_id": generation,
        "visibility_class": "confidential_strict_eval_only",
        "strict_row_count": 6,
        "source_stages": source_entries,
        "artifact_contract": contracts,
        "model_selection_access": False,
        "plaintext_mirror_materialized": False,
        "training_eligible_rows": 0,
        "authority": dict(S.AUTHORITY),
    }
    manifest_payload = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii") + b"\n"
    (directory / "manifest.json").write_bytes(manifest_payload)
    complete_payload = json.dumps({
        "generation_id": generation,
        "manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "artifact_count": len(contracts) + 1,
    }, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    (directory / "COMPLETE").write_bytes(complete_payload)
    for name in ("manifest.json", "COMPLETE"):
        (directory / name).chmod(0o600)
    directory.chmod(0o500)
    return generation, hashlib.sha256(manifest_payload).hexdigest()


def test_confidential_strict_loader_authenticates_complete_artifact_set_and_tamper(
    tmp_path: Path, monkeypatch,
):
    monkeypatch.setattr(S, "EXPECTED_STRICT_ROWS", 6)
    generation, manifest_sha = write_strict_generation(tmp_path / "ok")
    loaded, binding = S.load_confidential_strict_generation(
        tmp_path / "ok", generation,
        expected_manifest_sha256=manifest_sha,
    )
    assert [item.stage for item in loaded] == list(S.STRICT_SOURCE_STAGES)
    assert sum(len(item.rows) for item in loaded) == 6
    assert binding["generation_id"] == generation

    extra_root = tmp_path / "extra"
    extra_generation, extra_manifest_sha = write_strict_generation(extra_root)
    extra_dir = extra_root / extra_generation
    extra_dir.chmod(0o700)
    (extra_dir / "unexpected.json").write_text("{}")
    (extra_dir / "unexpected.json").chmod(0o600)
    extra_dir.chmod(0o500)
    with pytest.raises(S.Stage12700Error, match="file_set_invalid"):
        S.load_confidential_strict_generation(
            extra_root, extra_generation,
            expected_manifest_sha256=extra_manifest_sha,
        )

    tamper_root = tmp_path / "tamper"
    tamper_generation, tamper_manifest_sha = write_strict_generation(tamper_root)
    tamper_dir = tamper_root / tamper_generation
    tamper_dir.chmod(0o700)
    target = tamper_dir / "stage12687_strict_rows.jsonl"
    target.chmod(0o600)
    target.write_bytes(target.read_bytes() + b"{}\n")
    tamper_dir.chmod(0o500)
    with pytest.raises(S.Stage12700Error, match="artifact_(digest|size)"):
        S.load_confidential_strict_generation(
            tamper_root, tamper_generation,
            expected_manifest_sha256=tamper_manifest_sha,
        )


def test_split_core_loader_rejects_hash_mismatch_and_path_substitution(
    tmp_path: Path,
):
    copied = tmp_path / "split_core.py"
    copied.write_bytes(S.CORE_PATH.read_bytes())
    with pytest.raises(S.Stage12700Error, match="source_digest_mismatch"):
        S._read_pinned_core_source(copied, "0" * 64)

    substituted = tmp_path / "substituted_core.py"
    substituted.symlink_to(S.CORE_PATH)
    with pytest.raises(OSError):
        S._read_pinned_core_source(substituted, S.CORE_SHA256)


def test_private_loader_requires_complete_regular_digest_bound_generation(tmp_path: Path):
    candidate = private_candidate(
        12699, "historical_multilingual_exact_source_span_infilling",
    )
    generation, digest = write_private_generation(tmp_path, 12699, [candidate])
    bundle, binding = S.load_private_generation(
        tmp_path, generation, stage=12699, expected_bundle_sha256=digest,
    )
    assert bundle["candidates"] == [candidate]
    assert binding["private_materialization_sha256"] == digest

    with pytest.raises(S.Stage12700Error, match="artifact_digest_mismatch"):
        S.load_private_generation(
            tmp_path, generation, stage=12699, expected_bundle_sha256="0" * 64,
        )
    (tmp_path / generation / "COMPLETE").unlink()
    with pytest.raises(FileNotFoundError):
        S.load_private_generation(
            tmp_path, generation, stage=12699, expected_bundle_sha256=digest,
        )


def test_private_loader_rejects_symlink_leaf(tmp_path: Path):
    generation, digest = write_private_generation(
        tmp_path, 12699, [
            private_candidate(
                12699, "historical_multilingual_exact_source_span_infilling",
            )
        ],
    )
    complete = tmp_path / generation / "COMPLETE"
    real = tmp_path / generation / "REAL"
    complete.rename(real)
    complete.symlink_to(real.name)
    with pytest.raises(OSError):
        S.load_private_generation(
            tmp_path, generation, stage=12699, expected_bundle_sha256=digest,
        )


def test_private_adapter_preserves_proof_and_target_independent_identity():
    candidate = private_candidate(
        12699, "historical_multilingual_exact_source_span_infilling",
    )
    first = S.adapt_private_stage({"candidates": [candidate]}, 12699)
    mutated = json.loads(json.dumps(candidate))
    mutated["target"] = {"decoder_text": "different authenticated value"}
    second = S.adapt_private_stage({"candidates": [mutated]}, 12699)
    assert first.rows[0]["row_id"] == second.rows[0]["row_id"]
    assert first.ledger[0]["private_source_proof"] == candidate["proof"]
    assert first.ledger[0]["target_sha256"] != second.ledger[0]["target_sha256"]


def test_stage12698_metadata_subobjective_is_promoted_to_release_objective():
    candidate = private_candidate(
        12698,
        "exact_repository_metadata_classification",
        target={"classification_field": "repository_structure", "class": "flat"},
    )
    adapted = S.adapt_private_stage({"candidates": [candidate]}, 12698)
    assert adapted.rows[0]["objective_family"] == "repository_structure_classification"


def test_caller_cannot_supply_synthetic_stage12701_authority(
    tmp_path: Path, monkeypatch,
):
    parameters = inspect.signature(S.materialize_and_persist).parameters
    assert not any(name.startswith("stage12701") for name in parameters)
    blocked = S.materialize_and_persist(
        output_root=tmp_path,
        stage12698_root=tmp_path,
        stage12698_generation="synthetic",
        stage12698_sha256="0" * 64,
        stage12699_root=tmp_path,
        stage12699_generation="synthetic",
        stage12699_sha256="0" * 64,
        requested_rows=20,
    )
    assert blocked["decision"] == "BLOCKED_REVIEWED_STAGE12701_BINDING_REQUIRED"
    assert blocked["publication_performed"] is False
    assert blocked["knowledge_admission_eligible"] is False
    assert list(tmp_path.iterdir()) == []

    monkeypatch.setattr(
        S,
        "REVIEWED_STAGE12701_BINDING",
        S.ReviewedStage12701Binding(
            root="/caller-synthetic",
            generation_id="a" * 64,
            manifest_sha256="b" * 64,
            complete_sha256="c" * 64,
            review_contract="caller_claimed_review",
            independent_review_sha256="d" * 64,
        ),
    )
    rejected = S.materialize_and_persist(
        output_root=tmp_path, stage12698_root=tmp_path,
        stage12698_generation="synthetic", stage12698_sha256="0" * 64,
        stage12699_root=tmp_path, stage12699_generation="synthetic",
        stage12699_sha256="0" * 64, requested_rows=20,
    )
    assert (
        rejected["decision"]
        == "BLOCKED_REVIEWED_STAGE12701_BINDING_INVALID"
    )
    assert list(tmp_path.iterdir()) == []

def test_production_path_owns_publication_and_preserves_transaction(
    tmp_path: Path, monkeypatch,
):
    inputs = all_inputs()
    by_stage = {item.stage: item for item in inputs}
    public = {
        stage: subset_artifact(
            by_stage[stage], lambda row: row["split"] != "strict_eval",
        )
        for stage in S.STRICT_SOURCE_STAGES
    }
    strict = tuple(
        subset_artifact(
            by_stage[stage], lambda row: row["split"] == "strict_eval",
        )
        for stage in S.STRICT_SOURCE_STAGES
    )
    reviewed = S.ReviewedStage12701Binding(
        root="/reviewed-stage12701",
        generation_id="a" * 64,
        manifest_sha256="b" * 64,
        complete_sha256="c" * 64,
        review_contract="parent_production_and_independent_review_v1",
        independent_review_sha256="f" * 64,
    )
    monkeypatch.setattr(S, "REVIEWED_STAGE12701_BINDING", reviewed)
    monkeypatch.setattr(
        S, "load_public_stage",
        lambda root, stage, expected_summary_sha256: public[stage],
    )
    monkeypatch.setattr(
        S, "load_private_generation",
        lambda root, generation, *, stage, expected_bundle_sha256:
            ({"stage": stage}, {"stage": stage, "generation": generation}),
    )
    monkeypatch.setattr(
        S, "adapt_private_stage",
        lambda bundle, stage: by_stage[stage],
    )
    monkeypatch.setattr(
        S, "load_confidential_strict_generation",
        lambda root, generation, *, expected_manifest_sha256: (
            strict,
            {
                "generation_id": reviewed.generation_id,
                "manifest_sha256": reviewed.manifest_sha256,
                "complete_sha256": reviewed.complete_sha256,
            },
        ),
    )
    output_root = tmp_path / "release"
    output_root.mkdir(mode=0o700)
    revalidations = []
    real_revalidate = S._revalidate_core_source_identity
    monkeypatch.setattr(
        S, "_revalidate_core_source_identity",
        lambda: (revalidations.append(True), real_revalidate()),
    )
    kwargs = {
        "output_root": output_root,
        "stage12698_root": tmp_path,
        "stage12698_generation": "stage12698_fixture",
        "stage12698_sha256": "d" * 64,
        "stage12699_root": tmp_path,
        "stage12699_generation": "stage12699_fixture",
        "stage12699_sha256": "e" * 64,
        "requested_rows": 20,
    }
    assert not hasattr(S, "_publish_validated_release")
    persisted = S.materialize_and_persist(**kwargs)
    generation = output_root / persisted["generation"]
    assert (generation / "COMPLETE").is_file()
    assert generation.stat().st_mode & 0o777 == 0o500
    manifest = json.loads((generation / "release_manifest.json").read_text())
    assert (
        manifest["source_bindings"]["stage12694_split_core"]["sha256"]
        == S.CORE_SHA256
    )
    assert manifest["knowledge_admission_eligible"] is False
    assert not any(manifest["authority"].values())
    assert revalidations == [True]
    with pytest.raises(S.Stage12700Error, match="destination_collision"):
        S.materialize_and_persist(**kwargs)


def test_release_rejects_missing_objective_and_non_exact_geometry():
    inputs = all_inputs()
    reduced = [
        artifact(
            12698,
            [STAGE_OBJECTIVES[12698][1], *STAGE_OBJECTIVES[12698][1:]],
        )
        if item.stage == 12698 else item
        for item in inputs
    ]
    with pytest.raises(S.Stage12700Error, match="required_objective_family_missing"):
        S.build_release(
            reduced, requested_rows=20, source_bindings={}, strict_audit=None,
            authenticated_strict_row_refs=authenticated_strict_refs(reduced),
        )
    with pytest.raises(S.Stage12700Error, match="multiple_of_ten"):
        S.build_release(
            inputs, requested_rows=19, source_bindings={}, strict_audit=None,
            authenticated_strict_row_refs=authenticated_strict_refs(inputs),
        )


def test_missing_private_generation_fails_closed(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        S.load_private_generation(
            tmp_path, "stage12698_absent", stage=12698,
            expected_bundle_sha256="0" * 64,
        )
def test_public_loader_authenticates_summary_generation_and_jsonl(tmp_path: Path):
    item = artifact(12687, ["python_parser_source_span_infilling"])
    generation_id = "fixture12687"
    generation = tmp_path / "private" / generation_id
    generation.mkdir(parents=True)
    records_by_name = dict(zip(
        S.PUBLIC_FILES[12687],
        (item.rows, item.ledger, item.catalog),
        strict=True,
    ))
    contract = {}
    for name, records in records_by_name.items():
        payload = b"".join(
            json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            ).encode("ascii") + b"\n"
            for row in records
        )
        (generation / name).write_bytes(payload)
        contract[name] = {
            "relative_path": f"private/{generation_id}/{name}",
            "rows": len(records),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    summary = {
        "artifact_schema_version": S.CORE.STAGE_SCHEMAS[12687],
        "generation_id": generation_id,
        "generation_relative_path": f"private/{generation_id}",
        "artifact_contract": contract,
    }
    summary_payload = json.dumps(
        summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")
    (tmp_path / "summary.json").write_bytes(summary_payload)
    loaded = S.load_public_stage(
        tmp_path, 12687,
        expected_summary_sha256=hashlib.sha256(summary_payload).hexdigest(),
    )
    assert loaded.rows == item.rows
    assert loaded.ledger == item.ledger
    assert loaded.catalog == item.catalog
    with pytest.raises(S.Stage12700Error, match="artifact_digest_mismatch"):
        S.load_public_stage(
            tmp_path, 12687, expected_summary_sha256="0" * 64,
        )


def test_public_loader_rejects_symlink_generation(tmp_path: Path):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "fixture12687").symlink_to(real, target_is_directory=True)
    summary = {
        "artifact_schema_version": S.CORE.STAGE_SCHEMAS[12687],
        "generation_id": "fixture12687",
        "generation_relative_path": "private/fixture12687",
        "artifact_contract": {},
    }
    payload = json.dumps(summary).encode()
    (tmp_path / "summary.json").write_bytes(payload)
    with pytest.raises(OSError):
        S.load_public_stage(
            tmp_path, 12687,
            expected_summary_sha256=hashlib.sha256(payload).hexdigest(),
        )
