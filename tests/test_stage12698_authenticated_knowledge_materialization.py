from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12698_authenticated_knowledge_materialization.py"
SPEC = importlib.util.spec_from_file_location("stage12698_tested", SCRIPT)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = S
SPEC.loader.exec_module(S)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


def make_repo(root: Path, name: str, value: str) -> tuple[Path, str, str]:
    repo = root / name
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    (repo / "value.py").write_text(f"value = {value!r}\\n", encoding="utf-8")
    git(repo, "add", "value.py")
    git(repo, "commit", "-qm", "initial")
    revision = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    return repo, revision, tree


def memberships(records: list[dict]) -> dict:
    return {
        "stage12688_catalog": SimpleNamespace(records=tuple(records)),
        "stage12692_catalog": SimpleNamespace(records=()),
    }


def test_dependency_pins_load_exact_current_sources():
    stage12695, stage12696, stage12697 = S._load_dependencies()
    assert not any(stage12695.AUTHORITY.values())
    assert not any(stage12696.AUTHORITY.values())
    assert not any(stage12697.AUTHORITY.values())


def test_dependency_executes_the_hashed_bytes_not_reopened_path(tmp_path: Path):
    path = tmp_path / "dependency.py"
    path.write_text("VALUE = \"replaced\"\n", encoding="utf-8")
    trusted = b"VALUE = \"trusted\"\n"
    module = S._load_dependency_from_bytes(
        "race_fixture", path, trusted, S._sha(trusted),
    )
    assert module.VALUE == "trusted"


def test_repository_mapping_is_identity_based_and_deduplicated(tmp_path: Path):
    _stage12695, stage12696, _stage12697 = S._load_dependencies()
    root = tmp_path / "repos"
    root.mkdir()
    alpha, revision, tree = make_repo(root, "alpha", "one")
    make_repo(root, "unmatched", "two")
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", str(alpha), str(root / "alpha-copy")],
        check=True,
    )
    key = "1" * 64
    paths, report = S.resolve_repository_paths(
        stage12696,
        memberships([{
            "repository_key_sha256": key,
            "head_commit_git_oid": revision,
            "git_tree_oid": tree,
        }]),
        root,
    )
    assert paths[key] in {"alpha", "alpha-copy"}
    assert report["catalog_identities_resolved"] == 1
    assert report["duplicate_local_catalog_identity"] == 1
    assert report["catalog_unmatched_local_entries"] == 1
    assert str(root) not in json.dumps(report)


def test_repository_mapping_rejects_missing_accepted_identity(tmp_path: Path):
    _stage12695, stage12696, _stage12697 = S._load_dependencies()
    root = tmp_path / "repos"
    root.mkdir()
    make_repo(root, "only", "one")
    with pytest.raises(S.Stage12698Error, match="unresolved:1"):
        S.resolve_repository_paths(
            stage12696,
            memberships([{
                "repository_key_sha256": "1" * 64,
                "head_commit_git_oid": "f" * 40,
                "git_tree_oid": "e" * 40,
            }]),
            root,
        )


def test_repository_mapping_quarantines_symlink_entry(tmp_path: Path):
    _stage12695, stage12696, _stage12697 = S._load_dependencies()
    root = tmp_path / "repos"
    root.mkdir()
    repo, revision, tree = make_repo(root, "real", "one")
    (root / "alias").symlink_to(repo, target_is_directory=True)
    key = "1" * 64
    paths, report = S.resolve_repository_paths(
        stage12696,
        memberships([{
            "repository_key_sha256": key,
            "head_commit_git_oid": revision,
            "git_tree_oid": tree,
        }]),
        root,
    )
    assert paths == {key: "real"}
    assert report["local_entries_quarantined"] == 1


def test_real_stage12697_bundles_materialize_with_stage12695():
    stage12695, _stage12696, stage12697 = S._load_dependencies()
    verifier = stage12697.build_packages(ROOT)
    packages = {row["package_sha256"]: row for row in verifier["packages"]}
    rows = []
    seen: set[tuple[str, str, str]] = set()
    for bundle in verifier["materialization_inputs"]:
        package = packages[bundle["package_sha256"]]
        candidate = S._materialize_verifier_candidate(
            stage12695, stage12697, bundle, package,
        )
        rows.append(S._bind_verifier_repository_snapshot(
            candidate, bundle, package, seen,
        ))
    assert len(seen) == 3
    assert len(rows) == 3
    assert all(
        row["objective_family"] == "compact_observed_verifier_summary"
        for row in rows
    )
    assert all(not any(row["authority"].values()) for row in rows)
    assert "placeholder" not in json.dumps(rows).lower()


def _candidate(input_text: str, field: str | None = None) -> dict:
    if field is None:
        objective = "compact_observed_verifier_summary"
        target = {"framework": "pytest", "outcome": "pass"}
    else:
        objective = "exact_repository_metadata_classification"
        target = {"classification_field": field, "class": "observed"}
    return {
        "record_type": "test_candidate",
        "objective_family": objective,
        "input_text": input_text,
        "target": target,
        "proof": {"fixture": input_text},
        "authority": {**S.AUTHORITY, "stage12595_allowed": False},
    }


def _verifier_snapshot_evidence(
    commit: str, *, repo_family: str = "direct-verifier-repo",
    queue_id: str = "queue-direct",
) -> tuple[dict, dict]:
    repository_identity = hashlib.sha256(repo_family.encode()).hexdigest()
    snapshot = {
        "snapshot_contract": "descriptor_pinned_exact_shallow_head_only_v1",
        "repository_identity_sha256": repository_identity,
        "queue_id_sha256": hashlib.sha256(queue_id.encode()).hexdigest(),
        "revision": commit,
        "root_tree_oid": hashlib.sha1(
            ("tree:" + commit).encode(), usedforsecurity=False,
        ).hexdigest(),
        "declared_parent_oids": [],
        "parents_traversed": False,
        "shallow_boundary_sha256": "1" * 64,
        "tree_inventory": [],
        "blob_inventory": [],
        "gitlink_inventory": [],
        "tree_placements": 0,
        "blob_count": 0,
        "gitlink_count": 0,
        "total_entries": 0,
        "total_blob_bytes": 0,
    }
    snapshot["snapshot_commitment_sha256"] = S._stable([
        "stage12697_descriptor_pinned_shallow_head_snapshot_v1", snapshot,
    ])
    package = {
        "record_type":
            "stage12697_reviewed_local_observed_verifier_join_package_v2",
        "queue_id": queue_id,
        "repository_identity_sha256": repository_identity,
        "snapshot": snapshot,
    }
    package["package_sha256"] = S._stable(package)
    bundle = {
        "package_sha256": package["package_sha256"],
        "records": {"result": {
            "queue_id": queue_id,
            "repo_family": repo_family,
            "commit_sha": commit,
        }},
    }
    return package, bundle


def _reseal_package(package: dict) -> dict:
    copied = dict(package)
    copied.pop("package_sha256", None)
    copied["package_sha256"] = S._stable(copied)
    return copied


def test_verifier_repository_snapshot_direct_binding_and_adversarial_rejection():
    commit = "4" * 40
    candidate = {
        **_candidate("verifier"),
        "proof": {"immutable_commit_git_oid": commit},
    }
    package, bundle = _verifier_snapshot_evidence(commit)
    seen: set[tuple[str, str, str]] = set()
    bound = S._bind_verifier_repository_snapshot(
        candidate, bundle, package, seen,
    )
    assert bound["proof"]["repository_key_sha256"] == (
        package["repository_identity_sha256"]
    )
    assert bound["proof"]["revision"] == commit
    assert bound["proof"]["proof_contract"] == (
        "stage12697_direct_authenticated_repository_snapshot_v1"
    )

    forged_repository = dict(package)
    forged_repository["repository_identity_sha256"] = "f" * 64
    forged_repository = _reseal_package(forged_repository)
    forged_bundle = dict(bundle)
    forged_bundle["package_sha256"] = forged_repository["package_sha256"]
    with pytest.raises(S.Stage12698Error, match="snapshot_identity_mismatch"):
        S._bind_verifier_repository_snapshot(
            candidate, forged_bundle, forged_repository, set(),
        )

    forged_snapshot = dict(package)
    forged_snapshot["snapshot"] = dict(package["snapshot"])
    forged_snapshot["snapshot"]["root_tree_oid"] = "e" * 40
    forged_snapshot = _reseal_package(forged_snapshot)
    forged_bundle = dict(bundle)
    forged_bundle["package_sha256"] = forged_snapshot["package_sha256"]
    with pytest.raises(S.Stage12698Error, match="snapshot_commitment_mismatch"):
        S._bind_verifier_repository_snapshot(
            candidate, forged_bundle, forged_snapshot, set(),
        )

    with pytest.raises(S.Stage12698Error, match="identity_not_unique"):
        S._bind_verifier_repository_snapshot(
            candidate, bundle, package, seen,
        )


def test_supply_validator_requires_every_subobjective_and_no_placeholders(monkeypatch):
    monkeypatch.setattr(S, "EXPECTED_SOURCE_COUNTS", {
        "authenticated_git_heads": 1,
        "authenticated_declaration_rows": 1,
        "authenticated_verifier_joins": 1,
    })
    rows = [
        _candidate("meta:" + field, field)
        for field in sorted(S.EXPECTED_METADATA_FIELDS)
    ] + [_candidate("verifier")]
    dedup = {"raw_candidate_rows": 5, "unique_candidate_rows": 5}
    source_counts = dict(S.EXPECTED_SOURCE_COUNTS)
    counts = S._validate_materialized_supply(rows, dedup, source_counts)
    assert set(counts) == S.EXPECTED_METADATA_FIELDS
    with pytest.raises(S.Stage12698Error, match="candidate_supply_reconciliation"):
        S._validate_materialized_supply(
            rows[:-1],
            {"raw_candidate_rows": 5, "unique_candidate_rows": 4},
            source_counts,
        )
    duplicated = rows[:-1] + [dict(rows[0])]
    with pytest.raises(S.Stage12698Error, match="metadata_subobjective_count_mismatch"):
        S._validate_materialized_supply(
            duplicated,
            {"raw_candidate_rows": 5, "unique_candidate_rows": 5},
            source_counts,
        )
    missing_subobjective = [dict(row) for row in rows]
    missing_subobjective[0] = {
        **missing_subobjective[0],
        "target": {"classification_field": "unknown", "class": "present"},
    }
    with pytest.raises(S.Stage12698Error, match="subobjective_missing"):
        S._validate_materialized_supply(
            missing_subobjective, dedup, source_counts,
        )
    poisoned = [dict(row) for row in rows]
    poisoned[0] = {**poisoned[0], "target": {
        "classification_field": "repository_structure", "class": "PLACEHOLDER",
    }}
    with pytest.raises(S.Stage12698Error, match="placeholder_or_empty"):
        S._validate_materialized_supply(poisoned, dedup, source_counts)


def test_supply_validator_enforces_exact_production_objective_counts():
    rows = []
    expected = {
        "repository_structure": 476,
        "test_layout_convention": 476,
        "documentation_layout_convention": 476,
        "parsed_declaration_class": 172,
    }
    for field, count in expected.items():
        rows.extend(_candidate(f"{field}:{index}", field) for index in range(count))
    rows.extend(_candidate(f"verifier:{index}") for index in range(3))
    dedup = {
        "raw_candidate_rows": 3132,
        "unique_candidate_rows": 1603,
        "duplicate_or_conflicting_rows_quarantined": 1529,
        "conflicting_encoder_inputs": 0,
    }

    counts = S._validate_materialized_supply(
        rows, dedup, dict(S.EXPECTED_SOURCE_COUNTS),
    )

    assert len(rows) == 1603
    assert counts == expected


@pytest.mark.parametrize("sentinel", [
    "", "PLACEHOLDER", "<placeholder>", "__PLACEHOLDER__", "<missing>",
    "<answer>", "TODO", "TBD", "N/A", "stub", "unresolved", "...",
    "not implemented", "raise NotImplementedError()",
    "Answer: placeholder", " answer :  <missing> ", "Answer: TODO",
])
def test_supply_validator_rejects_semantic_target_placeholders(monkeypatch, sentinel):
    monkeypatch.setattr(S, "EXPECTED_SOURCE_COUNTS", {
        "authenticated_git_heads": 1,
        "authenticated_declaration_rows": 1,
        "authenticated_verifier_joins": 1,
    })
    rows = [
        _candidate("meta:" + field, field)
        for field in sorted(S.EXPECTED_METADATA_FIELDS)
    ] + [_candidate("verifier")]
    rows[0] = {**rows[0], "target": {
        "classification_field": "repository_structure", "class": sentinel,
    }}
    with pytest.raises(S.Stage12698Error, match="placeholder_or_empty"):
        S._validate_materialized_supply(
            rows,
            {"raw_candidate_rows": 5, "unique_candidate_rows": 5},
            dict(S.EXPECTED_SOURCE_COUNTS),
        )


def test_supply_validator_accepts_observed_verifier_outcome_pass(monkeypatch):
    monkeypatch.setattr(S, "EXPECTED_SOURCE_COUNTS", {
        "authenticated_git_heads": 1,
        "authenticated_declaration_rows": 1,
        "authenticated_verifier_joins": 1,
    })
    rows = [
        _candidate("meta:" + field, field)
        for field in sorted(S.EXPECTED_METADATA_FIELDS)
    ] + [_candidate("verifier")]
    assert rows[-1]["target"] == {"framework": "pytest", "outcome": "pass"}
    counts = S._validate_materialized_supply(
        rows,
        {"raw_candidate_rows": 5, "unique_candidate_rows": 5},
        dict(S.EXPECTED_SOURCE_COUNTS),
    )
    assert set(counts) == S.EXPECTED_METADATA_FIELDS


def test_supply_validator_ignores_non_target_placeholder_text(monkeypatch):
    monkeypatch.setattr(S, "EXPECTED_SOURCE_COUNTS", {
        "authenticated_git_heads": 1,
        "authenticated_declaration_rows": 1,
        "authenticated_verifier_joins": 1,
    })
    rows = [
        _candidate("meta:" + field, field)
        for field in sorted(S.EXPECTED_METADATA_FIELDS)
    ] + [_candidate("verifier")]
    dedup = {"raw_candidate_rows": 5, "unique_candidate_rows": 5}
    source_counts = dict(S.EXPECTED_SOURCE_COUNTS)
    expected = S._validate_materialized_supply(rows, dedup, source_counts)
    mutated = []
    for row in rows:
        changed = dict(row)
        changed["input"] = {
            "source": "Answer: placeholder; TODO; <missing>",
            "identifier": "legitimate_placeholder_adapter",
        }
        changed["provenance"] = {
            "comment": "Documents placeholder handling without being a target.",
        }
        mutated.append(changed)
    assert [row["target"] for row in mutated] == [row["target"] for row in rows]
    assert S._validate_materialized_supply(mutated, dedup, source_counts) == expected


@pytest.mark.parametrize("legitimate", [
    "placeholder_adapter", "replace placeholder in source", "stub_parser",
    "TODO comments are retained", "N/A is documented by the upstream API",
])
def test_supply_validator_allows_non_sentinel_target_text(monkeypatch, legitimate):
    monkeypatch.setattr(S, "EXPECTED_SOURCE_COUNTS", {
        "authenticated_git_heads": 1,
        "authenticated_declaration_rows": 1,
        "authenticated_verifier_joins": 1,
    })
    rows = [
        _candidate("meta:" + field, field)
        for field in sorted(S.EXPECTED_METADATA_FIELDS)
    ] + [_candidate("verifier")]
    rows[-1] = {**rows[-1], "target": {"summary": legitimate}}
    counts = S._validate_materialized_supply(
        rows,
        {"raw_candidate_rows": 5, "unique_candidate_rows": 5},
        dict(S.EXPECTED_SOURCE_COUNTS),
    )
    assert set(counts) == S.EXPECTED_METADATA_FIELDS


def test_materialize_authenticated_candidates_exercises_full_integration(monkeypatch):
    real_stage12695, _real_stage12696, _real_stage12697 = S._load_dependencies()
    repo_key = "1" * 64
    catalog_record = {
        "repository_key_sha256": repo_key,
        "content_component_sha256": "2" * 64,
        "revision": "4" * 40,
    }
    declaration_record = {"row_id": "declaration-1"}
    accepted = {
        "stage12688_catalog": SimpleNamespace(records=(catalog_record,)),
        "stage12692_rows": SimpleNamespace(records=(declaration_record,)),
    }
    evidence = SimpleNamespace(
        repository_key_sha256=repo_key,
        commit_oids=("4" * 40,),
        evidence_commitment_sha256="a" * 64,
        component_objects=(("blob", "2" * 40, 10),),
        component_tree_entry_identities=(("3" * 40, "100644", "blob", "2" * 40, "src/a.py"),),
        root_commit_oids=("4" * 40,),
    )
    declaration = SimpleNamespace(
        row_id="declaration-1", source_bytes=b"[project]\nname=\"demo\"\n",
    )
    inventory = SimpleNamespace(
        git_heads=(evidence,), declarations=(declaration,),
        capacity={"authenticated_git_heads": 1, "authenticated_declaration_rows": 1},
        package_manifest_sha256="5" * 64,
    )
    closed = []
    fake_stage12696 = SimpleNamespace(
        load_accepted_artifact_memberships=lambda _root: accepted,
        close_accepted_artifact_memberships=lambda value: closed.append(value),
        build_package_inventory=lambda **_kwargs: inventory,
    )
    fake_stage12695 = SimpleNamespace(
        build_git_metadata_candidates=lambda *_args, **_kwargs: [
            _candidate("meta:" + field, field)
            for field in ("repository_structure", "test_layout_convention",
                          "documentation_layout_convention")
        ],
        build_parsed_declaration_metadata_candidate=lambda *_args, **_kwargs:
            _candidate("meta:parsed_declaration_class", "parsed_declaration_class"),
        deduplicate_candidates=real_stage12695.deduplicate_candidates,
    )
    direct_package, direct_bundle = _verifier_snapshot_evidence(
        "5" * 40,
    )
    verifier = {
        "packages": [direct_package],
        "materialization_inputs": [direct_bundle],
        "capacity_commitment_sha256": "7" * 64,
    }
    fake_stage12697 = SimpleNamespace(build_packages=lambda _root: verifier)
    monkeypatch.setattr(S, "EXPECTED_SOURCE_COUNTS", {
        "authenticated_git_heads": 1,
        "authenticated_declaration_rows": 1,
        "authenticated_verifier_joins": 1,
    })
    monkeypatch.setattr(
        S, "_load_dependencies",
        lambda: (fake_stage12695, fake_stage12696, fake_stage12697),
    )
    monkeypatch.setattr(
        S, "resolve_repository_paths",
        lambda *_args, **_kwargs: ({repo_key: "repo"}, {"catalog_identities_resolved": 1}),
    )
    monkeypatch.setattr(
        S, "_materialize_verifier_candidate",
        lambda _s95, _s97, bundle, _package: {
            **_candidate("verifier"),
            "proof": {
                "immutable_commit_git_oid":
                    bundle["records"]["result"]["commit_sha"],
            },
        },
    )
    result = S.materialize_authenticated_candidates(Path("/unused"))
    assert result["candidate_count"] == 5
    verifier_row = next(
        row for row in result["candidates"]
        if row["objective_family"] == "compact_observed_verifier_summary"
    )
    assert verifier_row["proof"]["repository_key_sha256"] == (
        direct_package["repository_identity_sha256"]
    )
    assert verifier_row["proof"]["repository_key_sha256"] != repo_key
    assert verifier_row["proof"]["revision"] == "5" * 40
    assert verifier_row["proof"]["snapshot_commitment_sha256"] == (
        direct_package["snapshot"]["snapshot_commitment_sha256"]
    )
    assert result["deduplication"]["raw_candidate_rows"] == 5
    assert result["metadata_classification_counts"] == {
        field: 1 for field in sorted(S.EXPECTED_METADATA_FIELDS)
    }
    assert result["candidate_commitment_sha256"] != (
        result["model_example_commitment_sha256"]
    )
    assert closed == [accepted]
    assert not any(result["authority"].values())


def test_production_scale_reconciliation_proxy_without_repository_scan(monkeypatch):
    monkeypatch.setattr(S, "PRODUCTION_SOURCE_COUNTS", {})
    repo_count = 479
    declaration_count = 1692
    verifier_count = 3
    records = []
    evidences = []
    repository_paths = {}
    for index in range(repo_count):
        key = hashlib.sha256(f"repo:{index}".encode()).hexdigest()
        commit = f"{index + 1:040x}"
        records.append({
            "repository_key_sha256": key,
            "content_component_sha256":
                hashlib.sha256(f"component:{index}".encode()).hexdigest(),
            "revision": commit,
        })
        evidences.append(SimpleNamespace(
            repository_key_sha256=key,
            commit_oids=(commit,),
            evidence_commitment_sha256=
                hashlib.sha256(f"evidence:{index}".encode()).hexdigest(),
            component_objects=(("blob", f"{index + 500:040x}", 1),),
            component_tree_entry_identities=(
                (f"{index + 900:040x}", "100644", "blob",
                 f"{index + 500:040x}", f"src/{index}.py"),
            ),
            root_commit_oids=(commit,),
        ))
        repository_paths[key] = f"repo-{index:03d}"
    declaration_rows = [
        {"row_id": f"declaration:{index}"}
        for index in range(declaration_count)
    ]
    declaration_evidence = tuple(
        SimpleNamespace(
            row_id=row["row_id"],
            source_bytes=f"name = {index!r}\n".encode(),
        )
        for index, row in enumerate(declaration_rows)
    )
    accepted = {
        "stage12688_catalog": SimpleNamespace(records=tuple(records)),
        "stage12692_rows": SimpleNamespace(records=tuple(declaration_rows)),
    }
    inventory = SimpleNamespace(
        git_heads=tuple(evidences),
        declarations=declaration_evidence,
        capacity={
            "authenticated_git_heads": repo_count,
            "authenticated_declaration_rows": declaration_count,
        },
        package_manifest_sha256="5" * 64,
    )
    closed = []
    inventory_calls = []

    def build_inventory(**kwargs):
        inventory_calls.append(kwargs)
        assert kwargs["repository_paths"] == repository_paths
        return inventory

    fake_stage12696 = SimpleNamespace(
        load_accepted_artifact_memberships=lambda _root: accepted,
        close_accepted_artifact_memberships=lambda value: closed.append(value),
        build_package_inventory=build_inventory,
    )

    def metadata_candidates(record, **_kwargs):
        return [
            _candidate(
                f"{record['repository_key_sha256']}:{field}", field,
            )
            for field in (
                "repository_structure", "test_layout_convention",
                "documentation_layout_convention",
            )
        ]

    def declaration_candidate(row, **_kwargs):
        return _candidate(row["row_id"], "parsed_declaration_class")

    def deduplicate(rows):
        retained = []
        for row in rows:
            copied = dict(row)
            proof = dict(copied["proof"])
            proof["dedup_model_example_sha256"] = S._stable([
                copied["input_text"], copied["target"],
            ])
            copied["proof"] = proof
            retained.append(copied)
        return retained, {
            "raw_candidate_rows": len(rows),
            "unique_candidate_rows": len(retained),
            "duplicate_or_conflicting_rows_quarantined": 0,
            "conflicting_encoder_inputs": 0,
        }

    fake_stage12695 = SimpleNamespace(
        build_git_metadata_candidates=metadata_candidates,
        build_parsed_declaration_metadata_candidate=declaration_candidate,
        deduplicate_candidates=deduplicate,
    )
    bundles = []
    packages = []
    for index in range(verifier_count):
        package, bundle = _verifier_snapshot_evidence(
            f"{index + 1:040x}",
            repo_family=f"verifier-repo:{index}",
            queue_id=f"verifier-queue:{index}",
        )
        bundles.append(bundle)
        packages.append(package)
    verifier = {
        "packages": packages,
        "materialization_inputs": bundles,
        "capacity_commitment_sha256": "7" * 64,
    }
    fake_stage12697 = SimpleNamespace(build_packages=lambda _root: verifier)
    monkeypatch.setattr(
        S, "_load_dependencies",
        lambda: (fake_stage12695, fake_stage12696, fake_stage12697),
    )
    monkeypatch.setattr(
        S, "resolve_repository_paths",
        lambda *_args, **_kwargs: (
            repository_paths,
            {"catalog_identities_resolved": repo_count},
        ),
    )
    monkeypatch.setattr(
        S, "_materialize_verifier_candidate",
        lambda _s95, _s97, bundle, _package: {
            **_candidate(f"verifier:{bundle['package_sha256']}"),
            "proof": {
                "immutable_commit_git_oid":
                    bundle["records"]["result"]["commit_sha"],
            },
        },
    )

    result = S.materialize_authenticated_candidates(Path("/not-scanned"))

    assert len(inventory_calls) == 1
    assert result["source_counts"] == S.EXPECTED_SOURCE_COUNTS
    assert result["candidate_count"] == 3132
    assert result["deduplication"] == {
        "raw_candidate_rows": 3132,
        "unique_candidate_rows": 3132,
        "duplicate_or_conflicting_rows_quarantined": 0,
        "conflicting_encoder_inputs": 0,
    }
    assert result["metadata_classification_counts"] == {
        "documentation_layout_convention": 479,
        "parsed_declaration_class": 1692,
        "repository_structure": 479,
        "test_layout_convention": 479,
    }
    assert closed == [accepted]
    assert not any(result["authority"].values())


def test_private_materialization_is_immutable_complete_and_closed(
    tmp_path: Path, monkeypatch,
):
    monkeypatch.setattr(S, "EXPECTED_SOURCE_COUNTS", {
        "authenticated_git_heads": 1,
        "authenticated_declaration_rows": 1,
        "authenticated_verifier_joins": 1,
    })
    monkeypatch.setattr(S, "PRODUCTION_SOURCE_COUNTS", {})
    candidates = [
        _candidate("meta:" + field, field)
        for field in sorted(S.EXPECTED_METADATA_FIELDS)
    ] + [_candidate("verifier")]
    for candidate in candidates:
        candidate["proof"]["dedup_model_example_sha256"] = S._stable([
            candidate["input_text"], candidate["target"],
        ])
    dedup = {
        "raw_candidate_rows": 5,
        "unique_candidate_rows": 5,
        "duplicate_or_conflicting_rows_quarantined": 0,
        "conflicting_encoder_inputs": 0,
    }
    model_commitments = [
        row["proof"]["dedup_model_example_sha256"] for row in candidates
    ]
    result = {
        "stage": 12698,
        "record_type": "stage12698_authenticated_in_memory_materialization_v1",
        "candidates": candidates,
        "candidate_count": 5,
        "raw_candidate_count": 5,
        "duplicate_quarantine_count": 0,
        "candidate_commitment_sha256": S._stable(candidates),
        "model_example_commitment_sha256": S._stable(model_commitments),
        "objective_counts": {
            "compact_observed_verifier_summary": 1,
            "exact_repository_metadata_classification": 4,
        },
        "metadata_classification_counts": {
            field: 1 for field in S.EXPECTED_METADATA_FIELDS
        },
        "source_counts": dict(S.EXPECTED_SOURCE_COUNTS),
        "deduplication": dedup,
        "repository_mapping": {},
        "stage12696_package_manifest_sha256": "8" * 64,
        "stage12697_capacity_commitment_sha256": "9" * 64,
        "publication_performed": False,
        "training_eligible_rows": 0,
        "authority": dict(S.AUTHORITY),
    }
    monkeypatch.setattr(
        S, "materialize_authenticated_candidates", lambda _root: result,
    )
    summary, persisted = S.materialize_and_persist(Path("/unused"), tmp_path)
    generation = tmp_path / persisted["generation"]
    artifact = generation / "private_materialization.json"
    complete = generation / "COMPLETE"
    assert artifact.is_file() and complete.is_file()
    assert artifact.stat().st_mode & 0o777 == 0o400
    assert complete.stat().st_mode & 0o777 == 0o400
    assert generation.stat().st_mode & 0o777 == 0o500
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == (
        persisted["private_materialization_sha256"]
    )
    marker = json.loads(complete.read_text())
    assert marker["private_materialization_sha256"] == (
        persisted["private_materialization_sha256"]
    )
    bundle = json.loads(artifact.read_text())
    assert bundle["candidates"] == candidates
    assert bundle["residual_publication_trust_contract"] == (
        S.RESIDUAL_PUBLICATION_TRUST_CONTRACT
    )
    assert summary.get("candidates") is None
    assert not any(persisted["authority"].values())
    assert not hasattr(S, "persist_private_materialization")
    forged = dict(result)
    forged["reviewed"] = True
    with pytest.raises(S.Stage12698Error, match="private_result_schema_invalid"):
        S._validate_private_result(forged)


def test_private_materialization_exposes_no_arbitrary_result_publisher():
    assert not hasattr(S, "persist_private_materialization")
    assert not hasattr(S, "_persist_issued_private_materialization")
    assert not hasattr(S, "_persist_materialization")
    assert not hasattr(S, "_ISSUED_PUBLICATIONS")


def test_rename_noreplace_preserves_existing_destination(tmp_path: Path):
    (tmp_path / "source").write_bytes(b"source")
    (tmp_path / "destination").write_bytes(b"destination")
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(S.Stage12698Error, match="private_destination_exists"):
            S._rename_noreplace(directory_fd, "source", "destination")
    finally:
        os.close(directory_fd)
    assert (tmp_path / "source").read_bytes() == b"source"
    assert (tmp_path / "destination").read_bytes() == b"destination"


def test_generation_revalidation_detects_path_replacement(tmp_path: Path):
    root_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    os.mkdir("generation", mode=0o700, dir_fd=root_fd)
    generation_fd = os.open(
        "generation", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=root_fd,
    )
    info = os.fstat(generation_fd)
    os.rename("generation", "detached", src_dir_fd=root_fd, dst_dir_fd=root_fd)
    os.mkdir("generation", mode=0o700, dir_fd=root_fd)
    try:
        with pytest.raises(S.Stage12698Error, match="generation_identity_changed"):
            S._revalidate_generation(
                root_fd, "generation", generation_fd, (info.st_dev, info.st_ino),
            )
    finally:
        os.close(generation_fd)
        os.close(root_fd)


def _persist_for_filesystem_test(result, output_root, monkeypatch):
    monkeypatch.setattr(S, "_validate_private_result", lambda _result: None)
    monkeypatch.setattr(
        S, "materialize_authenticated_candidates", lambda _root: result,
    )
    return S.materialize_and_persist(Path("/unused"), output_root)[1]


def test_partial_write_leaves_no_complete_generation(tmp_path: Path, monkeypatch):
    candidates = [_candidate("private", "repository_structure")]
    result = {
        "candidates": candidates,
        "candidate_commitment_sha256": S._stable(candidates),
        "stage12696_package_manifest_sha256": "8" * 64,
        "stage12697_capacity_commitment_sha256": "9" * 64,
        "publication_performed": False,
        "training_eligible_rows": 0,
        "authority": dict(S.AUTHORITY),
    }
    monkeypatch.setattr(S.os, "write", lambda _fd, _payload: 0)
    with pytest.raises(S.Stage12698Error, match="short_write"):
        _persist_for_filesystem_test(result, tmp_path, monkeypatch)
    generations = list(tmp_path.iterdir())
    assert len(generations) == 1
    assert not (generations[0] / "COMPLETE").exists()


def test_private_materialization_rejects_missing_candidate_authority(tmp_path: Path):
    candidate = _candidate("private", "repository_structure")
    candidate["authority"] = {}
    candidates = [candidate]
    result = {
        "candidates": candidates,
        "candidate_commitment_sha256": S._stable(candidates),
        "stage12696_package_manifest_sha256": "8" * 64,
        "stage12697_capacity_commitment_sha256": "9" * 64,
        "publication_performed": False,
        "training_eligible_rows": 0,
        "authority": dict(S.AUTHORITY),
    }
    with pytest.raises(S.Stage12698Error, match="candidate_authority_not_closed"):
        S._validate_private_result(result)
    assert not list(tmp_path.iterdir())


def test_published_file_revalidation_detects_path_replacement(tmp_path: Path):
    original = tmp_path / "artifact"
    original.write_bytes(b"trusted")
    source_fd = os.open(original, os.O_RDONLY | os.O_NOFOLLOW)
    info = os.fstat(source_fd)
    original.rename(tmp_path / "detached")
    original.write_bytes(b"forged!")
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(S.Stage12698Error, match="published_identity_changed"):
            S._revalidate_published_file(
                directory_fd, "artifact", source_fd,
                (info.st_dev, info.st_ino), len(b"trusted"),
                hashlib.sha256(b"trusted").hexdigest(),
                "published_identity_changed",
            )
    finally:
        os.close(directory_fd)
        os.close(source_fd)


def test_published_file_revalidation_detects_equal_length_digest_change(tmp_path: Path):
    artifact = tmp_path / "artifact"
    artifact.write_bytes(b"trusted")
    source_fd = os.open(artifact, os.O_RDONLY | os.O_NOFOLLOW)
    info = os.fstat(source_fd)
    artifact.write_bytes(b"forged!")
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(S.Stage12698Error, match="published_digest_changed"):
            S._revalidate_published_file(
                directory_fd, "artifact", source_fd,
                (info.st_dev, info.st_ino), len(b"trusted"),
                hashlib.sha256(b"trusted").hexdigest(),
                "published_digest_changed",
            )
    finally:
        os.close(directory_fd)
        os.close(source_fd)


def test_private_result_rejects_reserved_top_level_authority():
    with pytest.raises(S.Stage12698Error, match="reserved_top_level_authority_field"):
        S._validate_private_result({"training_allowed": True})


def test_artifact_directory_entry_is_fsynced_before_complete_creation():
    source = S.SCRIPT_TEXT if hasattr(S, "SCRIPT_TEXT") else SCRIPT.read_text()
    artifact_validation = source.index(
        "generation_fd, \"private_materialization.json\", artifact_fd"
    )
    durability_barrier = source.index("os.fsync(generation_fd)", artifact_validation)
    complete_creation = source.index("complete = json.dumps", durability_barrier)
    assert artifact_validation < durability_barrier < complete_creation


def test_final_generation_rename_is_revalidated_and_parent_fsynced():
    source = S.SCRIPT_TEXT if hasattr(S, "SCRIPT_TEXT") else SCRIPT.read_text()
    mode_change = source.index("os.fchmod(generation_fd, 0o500)")
    child_fsync = source.index("os.fsync(generation_fd)", mode_change)
    rename = source.index(
        "root_handle.fd, temporary_generation, generation,", child_fsync,
    )
    assert mode_change < child_fsync < rename
    final_revalidation = source.index(
        "root_handle.fd, generation, generation_fd, generation_identity,", rename,
    )
    parent_fsync = source.index("os.fsync(root_handle.fd)", final_revalidation)
    assert rename < final_revalidation < parent_fsync


def test_private_materialization_rejects_symlink_root(tmp_path: Path, monkeypatch):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    candidates = [_candidate("private", "repository_structure")]
    result = {
        "candidates": candidates,
        "candidate_commitment_sha256": S._stable(candidates),
        "stage12696_package_manifest_sha256": "8" * 64,
        "stage12697_capacity_commitment_sha256": "9" * 64,
        "publication_performed": False,
        "training_eligible_rows": 0,
        "authority": dict(S.AUTHORITY),
    }
    with pytest.raises(RuntimeError, match="descriptor_root_pin_failed"):
        _persist_for_filesystem_test(result, alias, monkeypatch)


def test_public_summary_excludes_candidates_and_keeps_authority_closed():
    private = {
        "candidates": [{"input_text": "private"}],
        "candidate_count": 1,
        "publication_performed": False,
        "authority": dict(S.AUTHORITY),
    }
    public = S.public_summary(private)
    assert "candidates" not in public
    assert public["candidate_count"] == 1
    assert not any(public["authority"].values())


def test_cli_private_output_redacts_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    result = {
        "candidates": [{"private": "candidate"}],
        "candidate_count": 1,
        "publication_performed": False,
        "training_eligible_rows": 0,
        "authority": dict(S.AUTHORITY),
    }
    monkeypatch.setattr(
        S, "materialize_and_persist",
        lambda _repository_root, _output_root: (
            S.public_summary(result),
            {
                "private_materialization_performed": True,
                "publication_performed": False,
                "training_eligible_rows": 0,
                "authority": dict(S.AUTHORITY),
            },
        ),
    )
    assert S.main([
        "--materialize-in-memory", "--private-output-root", str(tmp_path),
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert "candidates" not in output
    assert output["private_artifact"]["private_materialization_performed"] is True
    assert '"private": "candidate"' not in json.dumps(output)


def test_cli_requires_explicit_materialization():
    with pytest.raises(SystemExit):
        S.main([])
