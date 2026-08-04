from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12694_global_knowledge_release_split_core.py"
SPEC = importlib.util.spec_from_file_location("stage12694", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage
SPEC.loader.exec_module(stage)


def hx(char: str, length: int = 64) -> str:
    return char * length


def artifact(
    number: int,
    repo: str,
    *,
    count: int,
    split: str,
    revision: str,
    tree: str,
    origin: str,
    files: tuple[str, ...] = (),
    objects: tuple[str, ...] = (),
    input_prefix: str | None = None,
) -> stage.StageArtifacts:
    repo = stage.stable(["repo", repo])
    component = stage.stable(["component", repo])
    catalog = ({
        "repository_key_sha256": repo,
        "content_component_sha256": component,
        "origin_url": origin,
        "revision": revision,
        "tree_oid": tree,
        "root_commit_git_oids": [revision],
        "source_file_sha256s": list(files),
        "source_git_blob_oids": list(objects),
        "split": split,
    },)
    rows = []
    proofs = []
    for index in range(count):
        row_id = f"r{number}_{index}"
        input_text = f"{input_prefix or row_id} input"
        target = f"target_{number}_{index}"
        rows.append({
            "row_id": row_id,
            "split": split,
            "objective_family": (
                "small_diff_exact_child_hunk_completion" if number == 12689
                else "python_symbol_reference_prediction" if number == 12690
                else "python_doc_reference_completion" if number == 12691
                else "declarative_test_build_target_resolution" if number == 12692
                else "exact_source_span_infilling"
            ),
            "input_text": input_text,
            "target": {"decoder_text": target},
            "source_provenance": {
                "repository_key_sha256": repo,
                "content_component_sha256": component,
                "revision": revision,
                "source_file_sha256": stage.stable([number, index, "file"]),
            },
        })
        proofs.append({
            "row_id": row_id,
            "split": split,
            "objective_family": rows[-1]["objective_family"],
            "repository_key_sha256": repo,
            "content_component_sha256": component,
            "revision": revision,
            "tree_oid": tree,
            "row_sha256": stage.stable(rows[-1]),
            "semantic_example_sha256": stage.stable([number, index, "semantic"]),
            "source_file_sha256": stage.stable([number, index, "file"]),
            "source_path": f"src/{number}_{index}.py",
            "source_start_byte": index * 10,
            "source_end_byte": index * 10 + 5,
            "candidate_evidence_sha256s": [stage.stable([number, index, "candidate"])],
            "patch_fingerprint_sha256": stage.stable([number, index, "patch"]),
        })
        input_sha = stage.hashlib.sha256(input_text.encode()).hexdigest()
        target_sha = stage.hashlib.sha256(target.encode()).hexdigest()
        if number == 12688:
            proofs[-1]["encoder_input_sha256"] = input_sha
        elif number != 12687:
            proofs[-1]["model_input_sha256"] = input_sha
        if number in {12687, 12688}:
            proofs[-1]["model_example_sha256"] = stage.stable([input_text, target])
        if number in {12687, 12688, 12689, 12691, 12698, 12699}:
            proofs[-1]["target_sha256"] = target_sha
    schema = stage.STAGE_SCHEMAS[number]
    return stage.StageArtifacts(
        number,
        schema,
        tuple(rows),
        tuple(proofs),
        catalog,
        catalog_commitment_sha256=stage._records_commitment(catalog),
        ledger_commitment_sha256=stage._records_commitment(proofs),
    )


def complete(items):
    by_stage = {item.stage: item for item in items}
    for number in stage.STAGE_SCHEMAS:
        if number not in by_stage:
            by_stage[number] = artifact(
                number,
                f"filler-{number}",
                count=1,
                split="train",
                revision=f"{number:040x}",
                tree=f"{number + 100:040x}",
                origin=f"https://fill/{number}",
            )
    return [by_stage[number] for number in sorted(by_stage)]


def build(items, *, requested_rows):
    return stage.build_global_split_core(
        complete(items), requested_rows=requested_rows
    )


def rebound(item, *, rows=None, ledger=None, catalog=None):
    rows = tuple(item.rows if rows is None else rows)
    ledger = tuple(item.ledger if ledger is None else ledger)
    catalog = tuple(item.catalog if catalog is None else catalog)
    return stage.StageArtifacts(
        item.stage,
        item.schema_version,
        rows,
        ledger,
        catalog,
        catalog_commitment_sha256=stage._records_commitment(catalog),
        ledger_commitment_sha256=stage._records_commitment(ledger),
    )


def with_atomic_evidence(item, index, *, field, value):
    rows = [dict(row) for row in item.rows]
    provenance = dict(rows[index]["source_provenance"])
    provenance[field] = value
    rows[index] = {**rows[index], "source_provenance": provenance}
    proofs = [dict(proof) for proof in item.ledger]
    proofs[index][field] = value
    proofs[index]["row_sha256"] = stage.stable(rows[index])
    return rebound(item, rows=rows, ledger=proofs)


def test_incompatible_schemas_normalize_and_override_conflicting_splits():
    shared_revision = hx("a", 40)
    first = artifact(12687, "repo-old", count=8, split="train", revision=shared_revision,
                     tree=hx("b", 40), origin="HTTPS://Example.COM/org/repo.git/")
    second = artifact(12690, "different-key", count=2, split="eval", revision=shared_revision,
                      tree=hx("c", 40), origin="ssh://git@example.com/org/repo")
    third = artifact(12692, "strict-repo", count=2, split="train", revision=hx("d", 40),
                     tree=hx("e", 40), origin="https://elsewhere/strict")
    fourth = artifact(12691, "eval-repo", count=2, split="train", revision=hx("f", 40),
                      tree=hx("1", 40), origin="https://elsewhere/eval")
    result = build(
        [first, second, third, fourth], requested_rows=10
    )
    assert result["planned_split_counts"] == {"eval": 1, "strict_eval": 1, "train": 8}
    assert len(result["cross_stage_split_conflicts"]) == 1
    shared = result["cross_stage_split_conflicts"][0]["global_component_id"]
    assert {ref["global_split"] for ref in result["row_reference_plan"]
            if ref["global_component_id"] == shared} == {"train"}
    assert any(ref["source_split"] != ref["global_split"] for ref in result["row_reference_plan"])


def test_same_mutable_origin_alone_never_unions_repositories():
    origin = "https://example.com/shared/repo.git"
    left = artifact(12687, "left", count=8, split="train", revision=hx("a", 40),
                    tree=hx("b", 40), origin=origin)
    right = artifact(12688, "right", count=2, split="eval", revision=hx("c", 40),
                     tree=hx("d", 40), origin=origin)
    extra = artifact(12689, "extra", count=2, split="strict_eval", revision=hx("e", 40),
                     tree=hx("f", 40), origin="https://other/extra")
    result = build([left, right, extra], requested_rows=10)
    matching = [component for component in result["global_components"]
                if component["canonical_origins_supplemental"] == ["https://example.com/shared/repo"]]
    assert len(matching) == 2


def test_weak_file_and_blob_evidence_never_unions_repositories():
    common = hx("9")
    left = artifact(12687, "left", count=8, split="train", revision=hx("a", 40),
                    tree=hx("b", 40), origin="https://one/left", files=(common,))
    right = artifact(12688, "right", count=2, split="eval", revision=hx("c", 40),
                     tree=hx("d", 40), origin="https://two/right", files=(common,))
    spare = artifact(12689, "spare", count=2, split="strict_eval", revision=hx("e", 40),
                     tree=hx("f", 40), origin="https://three/spare")
    result = build([left, right, spare], requested_rows=10)
    original_components = [
        component for component in result["global_components"]
        if any(node.startswith(("stage12687:", "stage12688:", "stage12689:"))
               for node in component["repository_nodes"])
    ]
    assert len(original_components) == 3

    left_object = artifact(
        12687, "left", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://one/left",
        files=(common,), objects=(hx("7", 40),),
    )
    right_object = artifact(
        12688, "right", count=2, split="eval", revision=hx("c", 40),
        tree=hx("d", 40), origin="https://two/right",
        files=(common,), objects=(hx("7", 40),),
    )
    union, repositories, _, _ = stage._build_components([left_object, right_object])
    assert len({union.find(node) for node in repositories}) == 2

    second_common = hx("8")
    left2 = artifact(12687, "left", count=8, split="train", revision=hx("a", 40),
                     tree=hx("b", 40), origin="https://one/left",
                     files=(common, second_common))
    right2 = artifact(12688, "right", count=2, split="eval", revision=hx("c", 40),
                      tree=hx("d", 40), origin="https://two/right",
                      files=(common, second_common))
    union, repositories, _, weak = stage._build_components([left2, right2])
    components = {union.find(node) for node in repositories}
    assert len(components) == 2
    assert all(weak[node] for node in repositories)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_file_sha256", hx("9")),
        ("source_git_blob_oid", hx("7", 40)),
    ],
)
def test_copied_atomic_weak_evidence_quarantines_only_direct_rows(field, value):
    left = artifact(
        12687, "left-direct", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/left-direct",
    )
    right = artifact(
        12688, "right-direct", count=4, split="eval", revision=hx("c", 40),
        tree=hx("d", 40), origin="https://x/right-direct",
    )
    left = with_atomic_evidence(left, 0, field=field, value=value)
    right = with_atomic_evidence(right, 0, field=field, value=value)
    result = build([left, right], requested_rows=10)
    direct_refs = {
        entry["row_ref"] for entry in result["quarantined_rows"]
        if "conflicting_atomic_weak_evidence" in entry["reasons"]
    }
    assert direct_refs == {
        "stage12687:r12687_0",
        "stage12688:r12688_0",
    }
    assert result["direct_weak_row_quarantine"]["row_count"] == 2
    assert "stage12687:r12687_1" not in {
        entry["row_ref"] for entry in result["quarantined_rows"]
    }
    assert "stage12688:r12688_1" not in {
        entry["row_ref"] for entry in result["quarantined_rows"]
    }


def test_direct_weak_quarantine_is_symmetric_and_order_independent():
    common = hx("9")
    left = with_atomic_evidence(
        artifact(
            12687, "left-order", count=8, split="train",
            revision=hx("a", 40), tree=hx("b", 40),
            origin="https://x/left-order",
        ),
        0, field="source_file_sha256", value=common,
    )
    right = with_atomic_evidence(
        artifact(
            12688, "right-order", count=4, split="eval",
            revision=hx("c", 40), tree=hx("d", 40),
            origin="https://x/right-order",
        ),
        0, field="source_file_sha256", value=common,
    )
    first = build([left, right], requested_rows=10)
    second = build([right, left], requested_rows=10)
    assert first["direct_weak_row_quarantine"] == second["direct_weak_row_quarantine"]
    assert first["quarantined_rows"] == second["quarantined_rows"]
    assert first["plan_commitment_sha256"] == second["plan_commitment_sha256"]


def test_missing_applicable_atomic_evidence_is_quarantined():
    item = artifact(
        12690, "missing-atomic", count=8, split="train",
        revision=hx("a", 40), tree=hx("b", 40),
        origin="https://x/missing-atomic",
    )
    rows = [dict(row) for row in item.rows]
    provenance = dict(rows[0]["source_provenance"])
    provenance.pop("source_file_sha256")
    rows[0] = {**rows[0], "source_provenance": provenance}
    proofs = [dict(proof) for proof in item.ledger]
    proofs[0].pop("source_file_sha256")
    proofs[0]["row_sha256"] = stage.stable(rows[0])
    result = build(
        [rebound(item, rows=rows, ledger=proofs)], requested_rows=10
    )
    rejected = next(
        entry for entry in result["quarantined_rows"]
        if entry["row_ref"] == "stage12690:r12690_0"
    )
    assert "missing_applicable_atomic_file_or_blob_evidence" in rejected["reasons"]


def test_final_overlap_audit_detects_cross_split_atomic_file_blob():
    shared = "file:" + hx("9")
    rows = {
        "stage12687:left": stage._NormalizedRow(
            12687, "left", "train", "left-node", hx("1"), hx("2"),
            (hx("3"),), (hx("4"),), (), (), (shared,), (), (),
        ),
        "stage12688:right": stage._NormalizedRow(
            12688, "right", "eval", "right-node", hx("5"), hx("6"),
            (hx("7"),), (hx("8"),), (), (), (shared,), (), (),
        ),
    }
    plan = [
        {
            "row_ref": "stage12687:left",
            "global_split": "train",
            "global_component_id": "left-component",
        },
        {
            "row_ref": "stage12688:right",
            "global_split": "eval",
            "global_component_id": "right-component",
        },
    ]
    with pytest.raises(stage.Stage12694Error, match="global_cross_split_overlap_nonzero"):
        stage._zero_overlap(plan, rows)


def test_forks_union_from_root_or_revision_despite_different_origins():
    revision = hx("a", 40)
    left = artifact(12687, "upstream", count=1, split="train", revision=revision,
                    tree=hx("b", 40), origin="https://host/upstream")
    right = artifact(12692, "fork", count=1, split="strict_eval", revision=revision,
                     tree=hx("c", 40), origin="https://host/fork")
    union, repositories, _, _ = stage._build_components([left, right])
    assert len({union.find(node) for node in repositories}) == 1


def test_global_duplicate_inputs_pairs_semantics_and_cross_component_evidence_quarantine_all():
    items = [
        artifact(12687, "a", count=11, split="train", revision=hx("a", 40),
                 tree=hx("b", 40), origin="https://x/a"),
        artifact(12688, "b", count=4, split="eval", revision=hx("c", 40),
                 tree=hx("d", 40), origin="https://x/b"),
        artifact(12689, "c", count=4, split="strict_eval", revision=hx("e", 40),
                 tree=hx("f", 40), origin="https://x/c"),
    ]
    rows0 = list(items[0].rows)
    rows1 = list(items[1].rows)
    rows1[0] = {**rows1[0], "input_text": rows0[0]["input_text"]}
    proofs1 = list(items[1].ledger)
    proofs1[0] = {
        **proofs1[0],
        "encoder_input_sha256": stage.hashlib.sha256(
            rows1[0]["input_text"].encode()
        ).hexdigest(),
        "model_example_sha256": stage.stable([
            rows1[0]["input_text"], rows1[0]["target"]["decoder_text"]
        ]),
        "row_sha256": stage.stable(rows1[0]),
    }
    proofs1[1] = {**proofs1[1], "semantic_example_sha256": items[0].ledger[1]["semantic_example_sha256"]}
    proofs1[2] = {**proofs1[2], "candidate_evidence_sha256s": items[0].ledger[2]["candidate_evidence_sha256s"]}
    items[1] = stage.StageArtifacts(
        12688,
        4,
        tuple(rows1),
        tuple(proofs1),
        items[1].catalog,
        catalog_commitment_sha256=items[1].catalog_commitment_sha256,
        ledger_commitment_sha256=stage._records_commitment(proofs1),
    )
    result = build(items, requested_rows=10)
    reasons = {entry["row_ref"]: entry["reasons"] for entry in result["quarantined_rows"]}
    assert "duplicate_encoder_input" in reasons["stage12687:r12687_0"]
    assert "duplicate_encoder_input" in reasons["stage12688:r12688_0"]
    assert "duplicate_semantic_evidence" in reasons["stage12687:r12687_1"]
    assert "duplicate_candidate_evidence" in reasons["stage12688:r12688_2"]
    assert all(value == 0 for value in result["global_overlap_counts"].values())


@pytest.mark.parametrize("bad,reason", [
    ("COMMIT_PLACEHOLDER", "unresolved_uppercase_placeholder"),
    ("THING_PLACEHOLDER", "unresolved_uppercase_placeholder"),
    ("Answer: <missing>", "unresolved_answer_marker"),
    ("pass", "stub_target"),
    ("raise NotImplementedError()", "stub_target"),
])
def test_explicit_placeholder_policy_rejects_unresolved_markers_and_stubs(bad, reason):
    assert stage.placeholder_rejection_reason(bad, target=True) == reason


@pytest.mark.parametrize("good", [
    "class Placeholder:\n    value = 1",
    "Placeholder identifiers are legitimate prose.",
    "placeholder UI parameters remain configurable",
    "return Placeholder(value)",
    "Answer: 42",
    "# TODO: preserve this source comment",
])
def test_explicit_placeholder_policy_preserves_legitimate_identifiers_and_prose(good):
    assert stage.placeholder_rejection_reason(good, target=True) is None


def test_strict_unavailable_keeps_every_authority_and_eligibility_false():
    inputs = [
        artifact(12687, "train", count=8, split="train", revision=hx("a", 40),
                 tree=hx("b", 40), origin="https://x/train"),
        artifact(12688, "eval", count=2, split="eval", revision=hx("c", 40),
                 tree=hx("d", 40), origin="https://x/eval"),
        artifact(12689, "strict", count=2, split="strict_eval", revision=hx("e", 40),
                 tree=hx("f", 40), origin="https://x/strict"),
    ]
    result = build(inputs, requested_rows=10)
    assert result["release_eligible"] is False
    assert result["strict_core_eligible"] is False
    assert result["training_eligible_rows"] == 0
    assert all(value is False for value in result["authority"].values())
    assert "confidential_strict_artifacts_unavailable" in result["release_blockers"]
    assert result["publication_performed"] is False
    assert result["source_artifacts_mutated"] is False


def test_commitment_mismatch_and_non_exact_geometry_fail_closed():
    item = artifact(12687, "repo", count=10, split="train", revision=hx("a", 40),
                    tree=hx("b", 40), origin="https://x/repo")
    bad = stage.StageArtifacts(
        item.stage, item.schema_version, item.rows, item.ledger, item.catalog,
        catalog_commitment_sha256=hx("0"),
        ledger_commitment_sha256=item.ledger_commitment_sha256,
    )
    with pytest.raises(stage.Stage12694Error, match="catalog_commitment_mismatch"):
        build([bad], requested_rows=10)
    with pytest.raises(stage.Stage12694Error, match="exact_80_10_10"):
        build([item], requested_rows=11)

def test_recorded_model_input_commitment_is_recomputed_and_must_match():
    item = artifact(
        12688, "repo", count=10, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/repo",
    )
    proofs = list(item.ledger)
    proofs[0] = {**proofs[0], "encoder_input_sha256": hx("0")}
    changed = stage.StageArtifacts(
        item.stage,
        item.schema_version,
        item.rows,
        tuple(proofs),
        item.catalog,
        catalog_commitment_sha256=item.catalog_commitment_sha256,
        ledger_commitment_sha256=stage._records_commitment(proofs),
    )
    with pytest.raises(stage.Stage12694Error, match="model_input_commitment_mismatch"):
        build([changed], requested_rows=10)



def test_result_is_deterministic_and_contains_only_row_references():
    inputs = [
        artifact(12687, "train", count=8, split="eval", revision=hx("a", 40),
                 tree=hx("b", 40), origin="https://x/train"),
        artifact(12688, "eval", count=2, split="train", revision=hx("c", 40),
                 tree=hx("d", 40), origin="https://x/eval"),
        artifact(12689, "strict", count=2, split="train", revision=hx("e", 40),
                 tree=hx("f", 40), origin="https://x/strict"),
    ]
    first = build(inputs, requested_rows=10)
    second = build(list(reversed(inputs)), requested_rows=10)
    assert first["plan_commitment_sha256"] == second["plan_commitment_sha256"]
    assert first["row_reference_plan"] == second["row_reference_plan"]
    assert all(set(ref) == {"row_ref", "source_split", "global_split", "global_component_id"}
               for ref in first["row_reference_plan"])


def test_main_is_bounded_and_cannot_publish():
    with pytest.raises(SystemExit, match="no_artifact_reads_no_publication_no_training"):
        stage.main()


def test_complete_release_requires_exact_stage_schema_map():
    items = complete([])
    with pytest.raises(stage.Stage12694Error, match="exact_stage_set"):
        stage.build_global_split_core(items[:-1], requested_rows=10)
    wrong = stage.StageArtifacts(
        items[0].stage,
        items[0].schema_version + 1,
        items[0].rows,
        items[0].ledger,
        items[0].catalog,
        catalog_commitment_sha256=items[0].catalog_commitment_sha256,
        ledger_commitment_sha256=items[0].ledger_commitment_sha256,
    )
    with pytest.raises(stage.Stage12694Error, match="unsupported_stage_or_schema"):
        stage.build_global_split_core([wrong, *items[1:]], requested_rows=10)


def test_actual_stage12687_ledger_omits_objective_and_binds_committed_row():
    item = artifact(
        12687, "actual-ledger", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/actual-ledger",
    )
    proofs = [dict(proof) for proof in item.ledger]
    for proof in proofs:
        proof.pop("objective_family")
    result = build([rebound(item, ledger=proofs)], requested_rows=10)
    assert result["planned_split_counts"] == {
        "train": 8,
        "eval": 1,
        "strict_eval": 1,
    }
    assert not any(
        entry["row_ref"].startswith("stage12687:")
        for entry in result["quarantined_rows"]
    )


def test_stage12687_optional_ledger_objective_must_match_row():
    item = artifact(
        12687, "objective-attack", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/objective-attack",
    )
    proofs = [dict(proof) for proof in item.ledger]
    proofs[0]["objective_family"] = "attacker_substituted_objective"
    with pytest.raises(stage.Stage12694Error, match="row_ledger_identity_mismatch"):
        build([rebound(item, ledger=proofs)], requested_rows=10)


def test_non_stage12687_ledger_objective_remains_required():
    item = artifact(
        12688, "required-objective", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/required-objective",
    )
    proofs = [dict(proof) for proof in item.ledger]
    proofs[0].pop("objective_family")
    with pytest.raises(stage.Stage12694Error, match="ledger_required_fields_missing"):
        build([rebound(item, ledger=proofs)], requested_rows=10)


def test_target_defect_does_not_change_assignment_and_exposes_deficit():
    primary = artifact(
        12687, "primary", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/primary",
    )
    baseline = build([primary], requested_rows=10)
    rows = [dict(row) for row in primary.rows]
    rows[0] = {**rows[0], "target": {"decoder_text": "pass"}}
    proofs = [dict(proof) for proof in primary.ledger]
    proofs[0] = {
        **proofs[0],
        "row_sha256": stage.stable(rows[0]),
        "model_example_sha256": stage.stable([rows[0]["input_text"], "pass"]),
        "target_sha256": stage.hashlib.sha256(b"pass").hexdigest(),
    }
    changed = build(
        [rebound(primary, rows=rows, ledger=proofs)], requested_rows=10
    )
    assert changed["component_assignments"] == baseline["component_assignments"]
    assert sum(changed["post_assignment_target_quarantine_split_deficits"].values()) == 1
    assert any(
        entry["row_ref"] == "stage12687:r12687_0"
        and entry["phase"] == "post_assignment_target"
        and "stub_target" in entry["reasons"]
        for entry in changed["quarantined_rows"]
    )


def test_missing_applicable_evidence_is_quarantined_not_vacuously_audited():
    item = artifact(
        12687, "evidence", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/evidence",
    )
    proofs = [dict(proof) for proof in item.ledger]
    proofs[0].pop("semantic_example_sha256")
    result = build([rebound(item, ledger=proofs)], requested_rows=10)
    rejected = next(
        entry for entry in result["quarantined_rows"]
        if entry["row_ref"] == "stage12687:r12687_0"
    )
    assert rejected["phase"] == "pre_assignment_input_or_evidence"
    assert "missing_semantic_evidence" in rejected["reasons"]
    assert all(value == 0 for value in result["global_overlap_counts"].values())


@pytest.mark.parametrize("length", [41, 48, 63])
def test_nonstandard_digest_lengths_are_rejected(length):
    item = artifact(
        12689, "history", count=2, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/history",
    )
    proofs = [dict(proof) for proof in item.ledger]
    proofs[0]["commit_git_oid"] = "a" * length
    with pytest.raises(stage.Stage12694Error, match="invalid_git_object_id"):
        build([rebound(item, ledger=proofs)], requested_rows=10)


def test_historical_git_identity_fields_accept_sha1_and_sha256():
    item = artifact(
        12689, "history", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/history",
    )
    fields = {
        "commit_git_oid": hx("1", 40),
        "parent_commit_git_oid": hx("2", 40),
        "commit_tree_git_oid": hx("3", 64),
        "parent_tree_git_oid": hx("4", 64),
        "head_commit_git_oid": hx("5", 40),
        "git_tree_oid": hx("6", 64),
    }
    catalog = [{**record, **fields} for record in item.catalog]
    proofs = [{**proof, **fields} for proof in item.ledger]
    result = build(
        [rebound(item, ledger=proofs, catalog=catalog)], requested_rows=10
    )
    history_node = "stage12689:" + proofs[0]["repository_key_sha256"]
    component = next(
        value for value in result["global_components"]
        if history_node in value["repository_nodes"]
    )
    assert component["strong_immutable_evidence_count"] >= len(fields)


def test_row_ledger_split_and_catalog_repository_must_agree():
    item = artifact(
        12690, "identity", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/identity",
    )
    proofs = [dict(proof) for proof in item.ledger]
    proofs[0]["split"] = "eval"
    with pytest.raises(stage.Stage12694Error, match="row_ledger_identity_mismatch"):
        build([rebound(item, ledger=proofs)], requested_rows=10)
    proofs = [dict(proof) for proof in item.ledger]
    proofs[0]["repository_key_sha256"] = hx("9")
    with pytest.raises(stage.Stage12694Error, match="absent_from_catalog"):
        build([rebound(item, ledger=proofs)], requested_rows=10)


@pytest.mark.parametrize(
    "missing",
    ["repository_key_sha256", "content_component_sha256", "revision"],
)
def test_row_source_provenance_identity_fields_are_mandatory(missing):
    item = artifact(
        12690, "provenance", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/provenance",
    )
    rows = [dict(row) for row in item.rows]
    provenance = dict(rows[0]["source_provenance"])
    provenance.pop(missing)
    rows[0] = {**rows[0], "source_provenance": provenance}
    proofs = [dict(proof) for proof in item.ledger]
    proofs[0]["row_sha256"] = stage.stable(rows[0])
    with pytest.raises(
        stage.Stage12694Error,
        match="row_source_provenance_identity_fields_missing",
    ):
        build([rebound(item, rows=rows, ledger=proofs)], requested_rows=10)


@pytest.mark.parametrize(
    "location",
    ["catalog_revision", "empty_catalog_revision", "ledger_git_oid"],
)
def test_git_identity_fields_reject_non_string_integers(location):
    item = artifact(
        12689, "typed-history", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/typed-history",
    )
    catalog = [dict(record) for record in item.catalog]
    proofs = [dict(proof) for proof in item.ledger]
    if location == "catalog_revision":
        catalog[0]["revision"] = 123
    elif location == "empty_catalog_revision":
        catalog[0]["revision"] = ""
    else:
        proofs[0]["commit_git_oid"] = 123
    expected = (
        "invalid_git_object_id_field"
        if location == "empty_catalog_revision"
        else "digest_identity_field_must_be_string"
    )
    with pytest.raises(stage.Stage12694Error, match=expected):
        build(
            [rebound(item, ledger=proofs, catalog=catalog)],
            requested_rows=10,
        )


def test_stale_target_and_row_commitments_reject():
    item = artifact(
        12691, "target", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/target",
    )
    rows = [dict(row) for row in item.rows]
    rows[0] = {**rows[0], "target": {"decoder_text": "changed"}}
    proofs = [dict(proof) for proof in item.ledger]
    proofs[0]["row_sha256"] = stage.stable(rows[0])
    with pytest.raises(stage.Stage12694Error, match="target_commitment_mismatch"):
        build([rebound(item, rows=rows, ledger=proofs)], requested_rows=10)


def test_stale_row_commitment_and_missing_required_fields_reject():
    item = artifact(
        12692, "row", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/row",
    )
    rows = [dict(row) for row in item.rows]
    rows[0] = {**rows[0], "input_text": "mutated input"}
    with pytest.raises(stage.Stage12694Error, match="row_commitment_mismatch"):
        build([rebound(item, rows=rows)], requested_rows=10)
    catalog = [dict(record) for record in item.catalog]
    catalog[0].pop("content_component_sha256")
    with pytest.raises(stage.Stage12694Error, match="catalog_required_fields_missing"):
        build([rebound(item, catalog=catalog)], requested_rows=10)


def test_strict_readiness_has_no_caller_controlled_bypass():
    item = artifact(
        12687, "strict", count=8, split="train", revision=hx("a", 40),
        tree=hx("b", 40), origin="https://x/strict",
    )
    with pytest.raises(TypeError):
        stage.StageArtifacts(
            item.stage,
            item.schema_version,
            item.rows,
            item.ledger,
            item.catalog,
            confidential_strict_available=True,
        )
    result = build([item], requested_rows=10)
    assert result["strict_core_eligible"] is False
    assert "coordinated_confidential_strict_rebuild_required" in result["release_blockers"]
