from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest


PATH = Path(__file__).parents[1] / "scripts/build_stage12701_confidential_strict_knowledge_materialization.py"
SPEC = importlib.util.spec_from_file_location("stage12701_tested", PATH)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = S
SPEC.loader.exec_module(S)


class FakeModule:
    MAX_REPOS = 1
    MAX_ROWS = 10

    @staticmethod
    def stable(value):
        return S._stable(value)


REPOSITORY = "a" * 64
COMPONENT = "b" * 64
REVISION = "c" * 40


def pair(index: int, *, split: str = "strict_eval"):
    repository = REPOSITORY if index == 0 else f"{index + 1:064x}"
    component = COMPONENT if index == 0 else f"{index + 101:064x}"
    revision = REVISION if index == 0 else f"{index + 1:040x}"
    row = {
        "row_id": f"row-{index}",
        "split": split,
        "input_text": f"input {index}",
        "target": {"decoder_text": f"target {index}"},
        "objective_family": "fixture_objective",
        "language_family": "fixture",
        "loss_mask": {"decoder_ce": True},
        "source_provenance": {
            "repository_key_sha256": repository,
            "content_component_sha256": component,
            "revision": revision,
        },
        "authority": dict(S.AUTHORITY),
    }
    proof = {
        "row_id": row["row_id"],
        "split": split,
        "objective_family": row["objective_family"],
        "repository_key_sha256": repository,
        "content_component_sha256": component,
        "revision": revision,
        "row_sha256": S._stable(row),
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
    }
    return row, proof


def catalog_entry(*, split: str = "strict_eval", repository: str = REPOSITORY,
                  component: str = COMPONENT, revision: str = REVISION):
    return {
        "repository_key_sha256": repository,
        "content_component_sha256": component,
        "revision": revision,
        "split": split,
    }


def fixture_contract(stage: int, splits=("strict_eval",)):
    pairs = [pair(index, split=split) for index, split in enumerate(splits)]
    rows = [value[0] for value in pairs]
    proofs = [value[1] for value in pairs]
    catalog = [
        catalog_entry(
            split=row["split"],
            repository=row["source_provenance"]["repository_key_sha256"],
            component=row["source_provenance"]["content_component_sha256"],
            revision=row["source_provenance"]["revision"],
        )
        for row in rows
    ]
    payloads = {"public.jsonl": b"public\n"}
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    commitment = S._stable(sorted(proof["row_sha256"] for proof in strict_proofs))
    summary = {
        "generation_id": f"g-{stage}",
        "reserved_unmaterialized_strict_row_count": len(strict_proofs),
        "strict_eval_commitment_sha256": commitment,
        "artifact_contract": {
            "public.jsonl": {"sha256": hashlib.sha256(payloads["public.jsonl"]).hexdigest()}
        },
    }
    prepared = SimpleNamespace(
        rows=rows,
        proofs=proofs,
        catalog=catalog,
        public_payloads=payloads,
        summary=summary,
    )
    spec = S.SourceSpec(
        stage,
        f"build_stage{stage}_fixture",
        "d" * 64,
        "e" * 64,
        1,
        len(rows),
        len(strict_proofs),
        "deterministically_replayed_not_originally_committed",
    )
    return FakeModule(), spec, prepared, summary


FIXTURE_SOURCE_PATHS = tuple(
    S.ROOT / "scripts" / f"{name}.py"
    for name in (
        "build_stage12687_source_backed_python_foundational_corpus",
        "build_stage12688_source_backed_multilingual_knowledge_corpus",
        "build_stage12689_source_backed_maintenance_history_corpus",
        "build_stage12690_source_backed_symbol_api_test_links",
        "build_stage12691_source_backed_python_api_doc_links",
        "build_stage12692_source_backed_declarative_test_build_conventions",
    )
)


def fixture_source_closure():
    result = {}
    for spec, path in zip(S.SOURCES, FIXTURE_SOURCE_PATHS, strict=True):
        info = path.stat()
        result[spec.module_name] = {
            "path": os.fspath(path),
            "device": info.st_dev,
            "inode": info.st_ino,
            "size": info.st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return result


def replay_record(stage: int, count: int):
    pairs = [pair(index) for index in range(count)]
    rows = [value[0] for value in pairs]
    proofs = [value[1] for value in pairs]
    catalog = [
        catalog_entry(
            repository=row["source_provenance"]["repository_key_sha256"],
            component=row["source_provenance"]["content_component_sha256"],
            revision=row["source_provenance"]["revision"],
        )
        for row in rows
    ]
    summary = {"generation_id": f"g-{stage}"}
    public_payloads = {"public.jsonl": b"public\n"}
    contract = S._snapshot_contract(
        rows, proofs, catalog, summary, public_payloads, rows, proofs, catalog
    )
    return {
        "stage": stage,
        "accepted_generation_id": f"g-{stage}",
        "accepted_summary_sha256": "a" * 64,
        "builder_sha256": "b" * 64,
        "replay_limits": {"max_repositories": 1, "max_rows": count},
        "strict_row_count": count,
        "accepted_strict_commitment_sha256": "c" * 64,
        "proof_authentication": "fixture",
        "rows": rows,
        "proofs": proofs,
        "catalog": catalog,
        "validated_snapshot_contract": contract,
        "validated_snapshot_commitment_sha256": S._stable(contract),
        "transitive_source_closure": fixture_source_closure(),
        "transitive_source_closure_sha256": S._stable(fixture_source_closure()),
    }


def tiny_replays(monkeypatch):
    monkeypatch.setattr(S, "EXPECTED_STRICT_ROWS", 6)
    monkeypatch.setattr(S, "SOURCES", tuple(
        S.SourceSpec(stage, f"build_stage{stage}_fixture", "b" * 64, "c" * 64, 1, 1, 1, "fixture")
        for stage in range(12687, 12693)
    ))
    return [replay_record(stage, 1) for stage in range(12687, 12693)]

def test_production_api_accepts_only_two_roots():
    assert tuple(inspect.signature(S.materialize_and_persist).parameters) == (
        "repository_root", "confidential_output_root"
    )


def test_frozen_sources_cover_exact_six_stages_and_9568_rows():
    assert [spec.stage for spec in S.SOURCES] == list(range(12687, 12693))
    assert sum(spec.strict_rows for spec in S.SOURCES) == 9_568
    assert all(len(spec.builder_sha256) == len(spec.summary_sha256) == 64 for spec in S.SOURCES)


def test_summary_paths_use_actual_artifact_roots():
    for spec in S.SOURCES:
        assert spec.summary_path == (
            S.ROOT
            / "runs/local/artifacts"
            / spec.module_name.removeprefix("build_")
            / "summary.json"
        )
        assert spec.summary_path.is_file()


def test_stale_sys_modules_entry_is_replaced_then_restored(monkeypatch):
    name = S.SOURCES[0].module_name
    stale = SimpleNamespace(stale=True)
    monkeypatch.setitem(sys.modules, name, stale)
    closure = S._load_frozen_closure()
    try:
        assert closure.modules[12687] is not stale
        assert sys.modules[name] is closure.modules[12687]
        assert set(closure.source_manifest()) == {spec.module_name for spec in S.SOURCES}
        assert {
            key: value["sha256"]
            for key, value in closure.source_manifest().items()
        } == {spec.module_name: spec.builder_sha256 for spec in S.SOURCES}
    finally:
        closure.close()
    assert sys.modules[name] is stale




def test_stage12689_dependency_is_canonical_and_private_name_is_absent():
    closure = S._load_frozen_closure()
    try:
        stage12687 = closure.modules[12687]
        stage12689 = closure.modules[12689]
        assert stage12689.S87 is stage12687
        assert stage12689.stable is stage12687.stable
        assert stage12689.git is stage12687.git
        assert S._PRIVATE_STAGE12689_DEPENDENCY not in sys.modules
        S._verify_frozen_closure(closure)
    finally:
        closure.close()


def test_stage12689_stale_private_dependency_is_restored(monkeypatch):
    stale = SimpleNamespace(stale=True)
    monkeypatch.setitem(sys.modules, S._PRIVATE_STAGE12689_DEPENDENCY, stale)
    closure = S._load_frozen_closure()
    try:
        assert S._PRIVATE_STAGE12689_DEPENDENCY not in sys.modules
    finally:
        closure.close()
    assert sys.modules[S._PRIVATE_STAGE12689_DEPENDENCY] is stale


def test_stage12689_private_dependency_uses_captured_not_live_bytes(
    tmp_path, monkeypatch
):
    pinned = b"VALUE = 'descriptor-captured'\n"
    live = tmp_path / "build_stage12687_fixture.py"
    live.write_bytes(b"raise RuntimeError('alternate live bytes executed')\n")
    spec = S.SourceSpec(
        12687, "build_stage12687_fixture", hashlib.sha256(pinned).hexdigest(),
        "e" * 64, 1, 1, 1, "fixture"
    )
    monkeypatch.setattr(
        S.SourceSpec, "builder_path", property(lambda self: live)
    )
    source = S.PinnedSource(spec, pinned, 1, 2, len(pinned))
    loader = S._PinnedDependencyLoader(source)
    module_spec = importlib.util.spec_from_loader(
        S._PRIVATE_STAGE12689_DEPENDENCY, loader
    )
    assert module_spec is not None
    module = importlib.util.module_from_spec(module_spec)
    loader.exec_module(module)
    assert module.VALUE == "descriptor-captured"
    assert module.__stage12701_pinned_source_sha256__ == spec.builder_sha256


def test_stage12689_private_dependency_exception_restores_state(monkeypatch):
    stale = SimpleNamespace(stale=True)
    monkeypatch.setitem(sys.modules, S._PRIVATE_STAGE12689_DEPENDENCY, stale)
    original_spec_loader = importlib.util.spec_from_file_location
    real_exec = S._PinnedDependencyLoader.exec_module

    def fail_after_exec(self, module):
        real_exec(self, module)
        raise RuntimeError("private_dependency_fixture_failure")

    monkeypatch.setattr(S._PinnedDependencyLoader, "exec_module", fail_after_exec)
    with pytest.raises(RuntimeError, match="private_dependency_fixture_failure"):
        S._load_frozen_closure()
    assert sys.modules[S._PRIVATE_STAGE12689_DEPENDENCY] is stale
    assert importlib.util.spec_from_file_location is original_spec_loader


def test_transitive_module_substitution_is_rejected():
    closure = S._load_frozen_closure()
    try:
        closure.modules[12691].stage12690 = SimpleNamespace(forged=True)
        with pytest.raises(S.Stage12701Error, match="transitive_dependency_substitution"):
            S._verify_frozen_closure(closure)
    finally:
        closure.close()


def test_validate_accepts_exact_fixture_replay():
    module, spec, prepared, summary = fixture_contract(12690)
    result = S._validate_prepared(module, spec, prepared, summary)
    assert result["strict_row_count"] == 1
    assert result["rows"][0]["split"] == "strict_eval"


@pytest.mark.parametrize("target", ["", " ", "placeholder", "Answer: TODO", "<missing>", "TBD", "N/A"])
def test_empty_and_placeholder_targets_are_rejected(target):
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.rows[0]["target"]["decoder_text"] = target
    prepared.proofs[0]["row_sha256"] = S._stable(prepared.rows[0])
    summary = copy.deepcopy(summary)
    summary["strict_eval_commitment_sha256"] = S._stable([prepared.proofs[0]["row_sha256"]])
    prepared.summary = summary
    with pytest.raises(S.Stage12701Error, match="placeholder_or_empty"):
        S._validate_prepared(module, spec, prepared, summary)


@pytest.mark.parametrize(
    "target",
    [
        "Answer:",
        "Answer:   ",
        "<TODO>",
        "[TBD]",
        "__TODO__",
        "TODO_FILL_ME",
        "TBD: pending",
        "PLACEHOLDER_VALUE",
        "__PLACEHOLDER__",
        "Answer: PLACEHOLDER_TOKEN",
        "TO_BE_FILLED",
    ],
)
def test_expanded_placeholder_variants_are_rejected(target):
    assert S._placeholder_target(target)


@pytest.mark.parametrize(
    "target",
    [
        "TODO: optimize parser allocation",
        "return placeholder_factory(value)",
        "The placeholder documents a real API parameter.",
        "answer: use the verified repository revision",
    ],
)
def test_legitimate_source_prose_is_not_a_placeholder(target):
    assert not S._placeholder_target(target)


def test_public_replay_mismatch_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    accepted = copy.deepcopy(summary)
    accepted["generation_id"] = "stale-head-generation"
    with pytest.raises(S.Stage12701Error, match="public_replay_mismatch"):
        S._validate_prepared(module, spec, prepared, accepted)


def test_relabelled_strict_row_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.rows[0]["split"] = "eval"
    with pytest.raises(S.Stage12701Error, match="row_proof_split_mismatch"):
        S._validate_prepared(module, spec, prepared, summary)


def test_proof_mutation_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.proofs[0]["row_sha256"] = "0" * 64
    with pytest.raises(S.Stage12701Error, match="row_digest_mismatch"):
        S._validate_prepared(module, spec, prepared, summary)


def test_catalog_mutation_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.catalog[0]["repository_key_sha256"] = "f" * 64
    with pytest.raises(S.Stage12701Error, match="proof_exact_catalog_identity_missing"):
        S._validate_prepared(module, spec, prepared, summary)



@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("repository_key_sha256", "not-a-hash", "catalog_repository_key_sha256_invalid"),
        ("content_component_sha256", "0" * 63, "catalog_content_component_sha256_invalid"),
        ("revision", "0" * 64, "catalog_revision_invalid"),
        ("split", "sealed_eval", "catalog_split_invalid"),
    ],
)
def test_catalog_identity_formats_are_enforced(field, value, error):
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.catalog[0][field] = value
    with pytest.raises(S.Stage12701Error, match=error):
        S._validate_prepared(module, spec, prepared, summary)


def test_strict_commitment_mutation_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    forged = copy.deepcopy(summary)
    forged["strict_eval_commitment_sha256"] = "0" * 64
    prepared.summary = forged
    with pytest.raises(S.Stage12701Error, match="strict_commitment_mismatch"):
        S._validate_prepared(module, spec, prepared, forged)


def test_public_payload_mutation_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.public_payloads["public.jsonl"] = b"forged\n"
    with pytest.raises(S.Stage12701Error, match="public_payload_hash_mismatch"):
        S._validate_prepared(module, spec, prepared, summary)


def test_full_row_and_proof_set_is_validated_before_strict_projection():
    module, spec, prepared, summary = fixture_contract(
        12690, splits=("train", "strict_eval")
    )
    result = S._validate_prepared(module, spec, prepared, summary)
    assert result["strict_row_count"] == 1
    assert [row["split"] for row in result["rows"]] == ["strict_eval"]
    assert result["validated_snapshot_contract"]["full_rows_sha256"] == S._stable(
        prepared.rows
    )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("split", "eval", "row_proof_split_mismatch"),
        ("objective_family", "other_objective", "row_proof_objective_mismatch"),
        ("repository_key_sha256", "f" * 64, "row_proof_repository_key_sha256_mismatch"),
        ("content_component_sha256", "f" * 64, "row_proof_content_component_sha256_mismatch"),
        ("revision", "f" * 40, "row_proof_revision_mismatch"),
    ],
)
def test_row_proof_identity_mismatches_are_rejected(field, value, error):
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.proofs[0][field] = value
    with pytest.raises(S.Stage12701Error, match=error):
        S._validate_prepared(module, spec, prepared, summary)


def test_unmatched_proof_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.proofs[0]["row_id"] = "unmatched-row"
    with pytest.raises(S.Stage12701Error, match="proof_without_matching_row"):
        S._validate_prepared(module, spec, prepared, summary)


def test_stage12687_unselected_strict_source_identity_is_accounted_and_excluded():
    module, spec, prepared, summary = fixture_contract(12687)
    unselected = catalog_entry(
        repository="9" * 64,
        component="8" * 64,
        revision="7" * 40,
    )
    prepared.catalog.append(unselected)

    result = S._validate_prepared(module, spec, prepared, summary)

    accounting = result["catalog_accounting"]
    strict_accounting = accounting["excluded_source_universe_by_split"]["strict_eval"]
    assert accounting["excluded_source_universe_contract"] == "source-universe-unselected"
    assert strict_accounting["identity_count"] == 1
    assert strict_accounting["identities_sha256"] == S._stable(
        [S._catalog_identity(unselected)]
    )
    assert result["catalog"] == [prepared.catalog[0]]
    assert result["validated_snapshot_contract"]["full_catalog_sha256"] == S._stable(
        prepared.catalog
    )
    assert result["validated_snapshot_contract"]["strict_catalog_sha256"] == S._stable(
        result["catalog"]
    )


def test_all_unselected_source_splits_are_accounted_and_excluded():
    module, spec, prepared, summary = fixture_contract(12690)
    excluded = [
        catalog_entry(
            split="train", repository="9" * 64, component="8" * 64, revision="7" * 40
        ),
        catalog_entry(
            split="eval", repository="6" * 64, component="5" * 64, revision="4" * 40
        ),
    ]
    prepared.catalog.extend(excluded)

    result = S._validate_prepared(module, spec, prepared, summary)

    accounting = result["catalog_accounting"]
    expected = sorted(S._catalog_identity(entry) for entry in excluded)
    assert accounting["excluded_source_universe_identity_count"] == 2
    assert accounting["excluded_source_universe_identities_sha256"] == S._stable(expected)
    assert accounting["excluded_source_universe_by_split"]["train"]["identity_count"] == 1
    assert accounting["excluded_source_universe_by_split"]["eval"]["identity_count"] == 1
    assert accounting["excluded_source_universe_by_split"]["strict_eval"]["identity_count"] == 0
    assert result["catalog"] == [prepared.catalog[0]]
    assert all(entry["split"] == "strict_eval" for entry in result["catalog"])


def test_stage12691_commitment_uses_full_strict_catalog_but_publishes_projection():
    module, spec, prepared, summary = fixture_contract(12691)
    unselected = catalog_entry(
        repository="9" * 64,
        component="8" * 64,
        revision="7" * 40,
    )
    prepared.catalog.append(unselected)
    strict_rows = [row for row in prepared.rows if row["split"] == "strict_eval"]
    strict_proofs = [proof for proof in prepared.proofs if proof["split"] == "strict_eval"]
    summary["strict_eval_commitment_sha256"] = module.stable({
        "contract": "stage12691_strict_eval_v2",
        "row_sha256s": sorted(module.stable(row) for row in strict_rows),
        "proof_sha256s": sorted(module.stable(proof) for proof in strict_proofs),
        "catalog_sha256s": sorted(module.stable(entry) for entry in prepared.catalog),
    })
    prepared.summary = copy.deepcopy(summary)

    result = S._validate_prepared(module, spec, prepared, summary)

    assert result["accepted_strict_commitment_sha256"] == summary[
        "strict_eval_commitment_sha256"
    ]
    assert result["catalog"] == [prepared.catalog[0]]
    assert unselected not in result["catalog"]


def test_strict_row_missing_exact_catalog_still_fails():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.catalog.clear()
    with pytest.raises(S.Stage12701Error, match="proof_exact_catalog_identity_missing"):
        S._validate_prepared(module, spec, prepared, summary)



def test_same_component_member_without_exact_row_identity_is_excluded():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.catalog.append(catalog_entry(repository="9" * 64))
    result = S._validate_prepared(module, spec, prepared, summary)
    accounting = result["catalog_accounting"]
    assert accounting["component_member_without_direct_row_count"] == 0
    assert accounting["excluded_source_universe_identity_count"] == 1
    assert accounting["excluded_source_universe_by_split"]["strict_eval"]["identity_count"] == 1
    assert "exact row-bound identities" in accounting["contract"]
    assert result["catalog"] == [prepared.catalog[0]]


def test_catalog_repository_conflict_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.catalog.append(catalog_entry(revision="f" * 40))
    with pytest.raises(S.Stage12701Error, match="catalog_repository_identity_conflict"):
        S._validate_prepared(module, spec, prepared, summary)


def test_exact_duplicate_catalog_entry_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.catalog.append(copy.deepcopy(prepared.catalog[0]))
    with pytest.raises(S.Stage12701Error, match="catalog_entry_duplicate"):
        S._validate_prepared(module, spec, prepared, summary)


def test_distinct_non_strict_lineage_records_may_share_lookup_identity():
    module, spec, prepared, summary = fixture_contract(12690)
    first = catalog_entry(
        split="train", repository="9" * 64, component="8" * 64, revision="7" * 40,
    )
    first["lineage_key_sha256s"] = ["1" * 64]
    second = copy.deepcopy(first)
    second["lineage_key_sha256s"] = ["2" * 64]
    prepared.catalog.extend([first, second])
    result = S._validate_prepared(module, spec, prepared, summary)
    assert result["strict_row_count"] == 1
    assert result["catalog"] == [prepared.catalog[0]]


def test_distinct_strict_lineage_records_cannot_share_lookup_identity():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.catalog[0]["lineage_key_sha256s"] = ["1" * 64]
    second = copy.deepcopy(prepared.catalog[0])
    second["lineage_key_sha256s"] = ["2" * 64]
    prepared.catalog.append(second)
    with pytest.raises(S.Stage12701Error, match="strict_catalog_identity_ambiguous"):
        S._validate_prepared(module, spec, prepared, summary)


def test_catalog_revision_must_exactly_bind_proof_and_row():
    module, spec, prepared, summary = fixture_contract(12690)
    prepared.catalog[0]["revision"] = "f" * 40
    with pytest.raises(S.Stage12701Error, match="proof_exact_catalog_identity_missing"):
        S._validate_prepared(module, spec, prepared, summary)


@pytest.mark.parametrize("collection", ["rows", "proofs", "catalog", "summary", "payloads"])
def test_prepared_collection_mutation_after_validation_cannot_change_snapshot(collection):
    module, spec, prepared, summary = fixture_contract(12690)
    if collection == "payloads":
        prepared.public_payloads["public.jsonl"] = bytearray(b"public\n")
    result = S._validate_prepared(module, spec, prepared, summary)
    before_commitment = result["validated_snapshot_commitment_sha256"]
    before_payloads = S._validated_payloads(result)
    if collection == "rows":
        prepared.rows[0]["target"]["decoder_text"] = "mutated"
    elif collection == "proofs":
        prepared.proofs[0]["row_sha256"] = "0" * 64
    elif collection == "catalog":
        prepared.catalog[0]["revision"] = "f" * 40
    elif collection == "summary":
        prepared.summary["generation_id"] = "mutated"
    else:
        prepared.public_payloads["public.jsonl"][0] = ord("X")
    assert result["validated_snapshot_commitment_sha256"] == before_commitment
    assert S._validated_payloads(result) == before_payloads


@pytest.mark.parametrize(
    ("collection", "error"),
    [
        ("rows", "validated_rows_mutated_before_publication"),
        ("proofs", "validated_proofs_mutated_before_publication"),
        ("catalog", "validated_catalog_mutated_before_publication"),
    ],
)
def test_replayed_collection_mutation_before_publication_is_rejected(collection, error):
    module, spec, prepared, summary = fixture_contract(12690)
    result = S._validate_prepared(module, spec, prepared, summary)
    result[collection][0]["mutation"] = True
    with pytest.raises(S.Stage12701Error, match=error):
        S._validated_payloads(result)


def test_validated_snapshot_contract_mutation_is_rejected():
    module, spec, prepared, summary = fixture_contract(12690)
    result = S._validate_prepared(module, spec, prepared, summary)
    result["validated_snapshot_contract"]["strict_rows_sha256"] = "0" * 64
    with pytest.raises(S.Stage12701Error, match="validated_snapshot_commitment_mismatch"):
        S._validated_payloads(result)


def test_builder_digest_mismatch_fails_before_execution(tmp_path, monkeypatch):
    builder = tmp_path / "builder.py"
    builder.write_text("VALUE = 1\n", encoding="ascii")
    spec = S.SourceSpec(1, "ignored", "0" * 64, "1" * 64, 1, 10, 1, "fixture")
    monkeypatch.setattr(S.SourceSpec, "builder_path", property(lambda self: builder))
    with pytest.raises(S.Stage12701Error, match="builder_digest_mismatch"):
        S._read_pinned_source(spec)


def test_descriptor_captured_bytes_execute_after_path_swap(tmp_path, monkeypatch):
    builder = tmp_path / "builder.py"
    original = b"VALUE = 1\n"
    builder.write_bytes(original)
    spec = S.SourceSpec(1, "stage12701_swap_fixture", hashlib.sha256(original).hexdigest(), "1" * 64, 1, 10, 1, "fixture")
    monkeypatch.setattr(S.SourceSpec, "builder_path", property(lambda self: builder))
    pinned = S._read_pinned_source(spec)
    replacement = tmp_path / "replacement.py"
    replacement.write_text("VALUE = 2\n", encoding="ascii")
    os.replace(replacement, builder)
    module = S._exec_pinned_module(pinned)
    try:
        assert module.VALUE == 1
        assert builder.read_text(encoding="ascii") == "VALUE = 2\n"
    finally:
        sys.modules.pop(spec.module_name, None)


def test_accepted_summary_symlink_is_rejected(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}\n", encoding="ascii")
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(S.Stage12701Error, match="accepted_summary_open_failed"):
        S._read_frozen_json(link, hashlib.sha256(b"{}\n").hexdigest())


def test_publish_creates_only_private_generation_with_final_modes(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    root = tmp_path / "confidential"
    manifest = S._publish(root, replayed)
    generation = root / manifest["generation_id"]
    assert generation.is_dir()
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE(generation.stat().st_mode) == 0o500
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o400 for path in generation.iterdir())
    assert (generation / "COMPLETE").is_file()
    assert not any(path.name.startswith(".pending-") for path in root.iterdir())
    assert manifest["strict_row_count"] == 6
    assert manifest["training_eligible_rows"] == 0
    assert not any(manifest["authority"].values())
    assert manifest["plaintext_mirror_materialized"] is False


def test_last_pre_rename_source_path_swap_is_rejected(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    source_paths = []
    closure = {}
    for index, spec in enumerate(S.SOURCES):
        source = tmp_path / f"source-{index}.py"
        source.write_text(f"VALUE = {index}\n", encoding="ascii")
        source_paths.append(source)
        info = source.stat()
        closure[spec.module_name] = {
            "path": os.fspath(source),
            "device": info.st_dev,
            "inode": info.st_ino,
            "size": info.st_size,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    for stage in replayed:
        stage["transitive_source_closure"] = copy.deepcopy(closure)
        stage["transitive_source_closure_sha256"] = S._stable(closure)
    real_revalidate = S._revalidate_transitive_source_paths
    rename_called = False

    def swap_then_revalidate(records):
        replacement = tmp_path / "replacement.py"
        replacement.write_text("VALUE = 'swapped'\n", encoding="ascii")
        os.replace(replacement, source_paths[0])
        real_revalidate(records)

    def track_rename(*args):
        nonlocal rename_called
        rename_called = True

    monkeypatch.setattr(S, "_revalidate_transitive_source_paths", swap_then_revalidate)
    monkeypatch.setattr(S, "_rename_noreplace", track_rename)
    with pytest.raises(S.Stage12701Error, match="source_path_inode_changed"):
        S._publish(tmp_path / "confidential", replayed)
    assert not rename_called


def test_manifest_states_residual_same_uid_writer_assumption(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    manifest = S._publish(tmp_path / "confidential", replayed)
    contract = manifest["publication_residual_trust_contract"]
    assert contract["universal_atomicity_claimed"] is False
    assert contract["hostile_same_uid_concurrent_writers_excluded"] is True
    assert "after the last pre-rename inode check" in contract["residual_assumption"]


def test_final_rename_is_commit_point_with_no_fallible_fsync_after(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    root = tmp_path / "confidential"
    real_rename = S._rename_noreplace
    real_fsync = S.os.fsync
    committed = False
    fsync_after_commit = 0

    def tracked_rename(*args):
        nonlocal committed
        real_rename(*args)
        committed = True

    def tracked_fsync(fd):
        nonlocal fsync_after_commit
        if committed:
            fsync_after_commit += 1
            raise OSError("postcommit fsync must not run")
        return real_fsync(fd)

    monkeypatch.setattr(S, "_rename_noreplace", tracked_rename)
    monkeypatch.setattr(S.os, "fsync", tracked_fsync)
    manifest = S._publish(root, replayed)
    assert (root / manifest["generation_id"] / "COMPLETE").is_file()
    assert fsync_after_commit == 0


def test_postcommit_cleanup_exception_cannot_revoke_generation(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    root = tmp_path / "confidential"
    real_rename = S._rename_noreplace
    real_close = S.os.close
    committed = False

    def tracked_rename(*args):
        nonlocal committed
        real_rename(*args)
        committed = True

    def failing_close(fd):
        if committed:
            real_close(fd)
            raise RuntimeError("injected postcommit cleanup failure")
        return real_close(fd)

    monkeypatch.setattr(S, "_rename_noreplace", tracked_rename)
    monkeypatch.setattr(S.os, "close", failing_close)
    manifest = S._publish(root, replayed)
    assert (root / manifest["generation_id"] / "COMPLETE").is_file()


def test_generation_collision_fails_without_overwrite(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    root = tmp_path / "confidential"
    manifest = S._publish(root, replayed)
    complete = (root / manifest["generation_id"] / "COMPLETE").read_bytes()
    with pytest.raises(S.Stage12701Error, match="generation_collision"):
        S._publish(root, replayed)
    assert (root / manifest["generation_id"] / "COMPLETE").read_bytes() == complete


def test_symlink_output_root_is_rejected(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "confidential"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        S._publish(link, replayed)
    assert not list(real.iterdir())


def test_rename_failure_leaves_no_complete_named_generation(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    root = tmp_path / "confidential"
    monkeypatch.setattr(S, "_rename_noreplace", lambda *args: (_ for _ in ()).throw(S.Stage12701Error("injected_rename_failure")))
    with pytest.raises(S.Stage12701Error, match="injected_rename_failure"):
        S._publish(root, replayed)
    assert not any(path.name.startswith("stage12701") or len(path.name) == 64 for path in root.iterdir())
    assert all(path.name.startswith(".pending-") for path in root.iterdir())


def test_interruption_before_complete_never_commits_generation(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    root = tmp_path / "confidential"
    original = S._write_file

    def interrupt(directory_fd, name, payload):
        if name == "COMPLETE":
            raise S.Stage12701Error("injected_interruption")
        return original(directory_fd, name, payload)

    monkeypatch.setattr(S, "_write_file", interrupt)
    with pytest.raises(S.Stage12701Error, match="injected_interruption"):
        S._publish(root, replayed)
    assert all(path.name.startswith(".pending-") for path in root.iterdir())


def test_temporary_generation_replacement_race_is_rejected(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    root = tmp_path / "confidential"
    real_stat = S.os.stat

    def forged_stat(path, *args, **kwargs):
        value = real_stat(path, *args, **kwargs)
        if isinstance(path, str) and path.startswith(".pending-"):
            values = list(value)
            values[1] += 1
            return os.stat_result(values)
        return value

    monkeypatch.setattr(S.os, "stat", forged_stat)
    with pytest.raises(S.Stage12701Error, match="temporary_generation_replaced"):
        S._publish(root, replayed)


def test_root_replacement_race_is_rejected(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    root = tmp_path / "confidential"
    real_stat = S.os.stat
    root_stats = 0

    def forged_stat(path, *args, **kwargs):
        nonlocal root_stats
        value = real_stat(path, *args, **kwargs)
        if path == "confidential":
            root_stats += 1
            if root_stats == 2:
                values = list(value)
                values[1] += 1
                return os.stat_result(values)
        return value

    monkeypatch.setattr(S.os, "stat", forged_stat)
    with pytest.raises(S.Stage12701Error, match="confidential_root_replaced"):
        S._publish(root, replayed)


def test_file_fsync_failure_prevents_commit(tmp_path, monkeypatch):
    replayed = tiny_replays(monkeypatch)
    root = tmp_path / "confidential"
    real_fsync = S.os.fsync
    calls = 0

    def fail_first(fd):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected fsync failure")
        return real_fsync(fd)

    monkeypatch.setattr(S.os, "fsync", fail_first)
    with pytest.raises(OSError, match="injected fsync failure"):
        S._publish(root, replayed)
    assert all(path.name.startswith(".pending-") for path in root.iterdir())


def test_materialize_revalidates_repository_root(tmp_path, monkeypatch):
    repository = tmp_path / "repositories"
    repository.mkdir()
    output = tmp_path / "confidential"
    replayed = tiny_replays(monkeypatch)
    records = iter(replayed)
    monkeypatch.setattr(S, "_replay_stage", lambda spec, root, closure: next(records))
    monkeypatch.setattr(
        S,
        "_load_frozen_closure",
        lambda: SimpleNamespace(close=lambda: None),
    )
    real_open = S._open_absolute_directory
    calls = 0

    def changed(path):
        nonlocal calls
        fd = real_open(path)
        calls += 1
        if calls == 2:
            original_fstat = S.os.fstat
            value = original_fstat(fd)
            monkeypatch.setattr(S.os, "fstat", lambda candidate: os.stat_result([value.st_mode, value.st_ino + 1, value.st_dev, value.st_nlink, value.st_uid, value.st_gid, value.st_size, value.st_atime, value.st_mtime, value.st_ctime]) if candidate == fd else original_fstat(candidate))
        return fd

    monkeypatch.setattr(S, "_open_absolute_directory", changed)
    with pytest.raises(S.Stage12701Error, match="repository_root_replaced"):
        S.materialize_and_persist(repository, output)
    assert not output.exists()


def test_no_production_artifact_or_plaintext_mirror_constant():
    source = PATH.read_text(encoding="ascii")
    assert "DEFAULT_OUTPUT" not in source
    assert "training_eligible_rows\": 0" in source
    assert "plaintext_mirror_materialized\": False" in source
