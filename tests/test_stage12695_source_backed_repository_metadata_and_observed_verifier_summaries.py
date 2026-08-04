"""Focused tests for the fail-closed Stage12695 evidence core."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / (
    "scripts/build_stage12695_source_backed_repository_metadata_and_observed_"
    "verifier_summaries.py"
)
SPEC = importlib.util.spec_from_file_location("stage12695", BUILDER)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def raw(record: dict) -> bytes:
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_oid(data: bytes) -> str:
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    return hashlib.sha1(payload).hexdigest()


def git_fixture() -> tuple[dict, list[list[object]], list[str], list[list[str]]]:
    objects: list[list[object]] = [
        ["blob", "1" * 40, 11],
        ["blob", "2" * 40, 29],
        ["commit", "3" * 40, None],
    ]
    roots = ["4" * 40]
    head = "5" * 40
    tree = "6" * 40
    trees = [tree, "7" * 40]
    lineage = [
        f"head:{head}",
        *(f"root:{oid}" for oid in roots),
        *(f"tree:{oid}" for oid in trees),
    ]
    record = {
        "repository_key_sha256": "8" * 64,
        "content_component_sha256": "9" * 64,
        "revision": head,
        "head_commit_git_oid": head,
        "git_tree_oid": tree,
        "tree_git_oids": sorted(trees),
        "root_commit_git_oids": roots,
        "hard_grouping_key_sha256s": [
            sha256(value.encode()) for value in sorted(set(lineage))
        ],
        "all_tree_object_count": len(objects),
        "tree_object_type_counts": {"blob": 2, "commit": 1},
        "all_tree_object_identity_inventory_sha256": stage._stable(objects),
        "split": "train",
    }
    entries = sorted([
        [tree, "100644", "blob", "1" * 40, "src/value.py"],
        [tree, "100644", "blob", "2" * 40, "docs/readme.md"],
        [tree, "160000", "commit", "3" * 40, "vendor/library"],
    ])
    return record, objects, roots, entries


def scalar_declaration_fixture(
    value: str = "demo",
) -> tuple[dict, bytes]:
    source = f'[project]\nname = "{value}"\n'.encode()
    start = source.index(value.encode())
    end = start + len(value)
    row = {
        "objective_family": "declarative_test_build_scalar_completion",
        "ecosystem": "python",
        "target": {"decoder_text": value},
        "source_provenance": {
            "parser_adapter": {
                "name": "stdlib_tomllib_pyproject",
                "version": "1",
            },
            "proof_contract": "exact_static_literal_scalar_completion_v1",
            "source_file_sha256": sha256(source),
            "source_git_blob_oid": git_blob_oid(source),
            "source_path": "pyproject.toml",
            "target_start_byte": start,
            "target_end_byte": end,
            "member_start_byte": source.index(b"name"),
            "member_end_byte": len(source),
            "repository_key_sha256": "a" * 64,
            "content_component_sha256": "b" * 64,
            "revision": "c" * 40,
        },
        "authority": dict(stage.AUTHORITY),
        "split": "train",
    }
    return row, source


def reference_declaration_fixture() -> tuple[dict, bytes]:
    source = b'{"scripts":{"test":"npm run lint","lint":"eslint ."}}'
    invocation_start = source.index(b"npm run lint")
    invocation_end = invocation_start + len(b"npm run lint")
    reference_start = source.index(b"lint", invocation_start)
    reference_end = reference_start + 4
    definition_start = source.index(b'"lint"', invocation_end) + 1
    definition_end = definition_start + 4
    command_start = source.index(b"eslint .")
    command_end = command_start + len(b"eslint .")
    candidate_start = definition_start - 1
    candidate_end = command_end + 1
    row = {
        "objective_family": "declarative_test_build_target_resolution",
        "ecosystem": "npm",
        "target": {"decoder_text": "candidate_0"},
        "source_provenance": {
            "parser_adapter": {
                "name": "stdlib_json_plus_byte_spans",
                "version": "1",
            },
            "proof_contract": "exact_literal_package_script_reference_v1",
            "source_file_sha256": sha256(source),
            "source_git_blob_oid": git_blob_oid(source),
            "source_path": "package.json",
            "reference_target_start_byte": reference_start,
            "reference_target_end_byte": reference_end,
            "definition_name_start_byte": definition_start,
            "definition_name_end_byte": definition_end,
            "definition_command_start_byte": command_start,
            "definition_command_end_byte": command_end,
            "invocation_command_start_byte": invocation_start,
            "invocation_command_end_byte": invocation_end,
            "candidate_definition_spans": [
                {"start_byte": candidate_start, "end_byte": candidate_end}
            ],
            "repository_key_sha256": "d" * 64,
            "content_component_sha256": "e" * 64,
            "revision": "f" * 40,
        },
        "authority": dict(stage.AUTHORITY),
        "split": "eval",
    }
    return row, source


def verifier_fixture(
    family: str = "pytest", outcome: str = "pass"
) -> dict[str, object]:
    queue = "queue-1"
    repo = "repo-1"
    checkout = "/tmp/stage12695/repo"
    commit = "a" * 40
    if family == "pytest":
        command = ["pytest", "tests/test_unit.py", "-q"]
        selected = ["tests/test_unit.py::test_ok"]
        if outcome == "pass":
            stdout, exit_code = "1 passed in 0.01s\n", 0
        elif outcome == "fail":
            stdout, exit_code = "1 failed in 0.01s\n", 1
        else:
            stdout, exit_code = "1 error in 0.01s\n", 1
    else:
        command = ["ctest", "-R", "^unit_case$", "--output-on-failure"]
        selected = ["unit_case"]
        if outcome == "pass":
            stdout, exit_code = (
                "1/1 Test #7: unit_case ................ Passed  0.01 sec\n"
                "100% tests passed, 0 tests failed out of 1\n"
                "Total Test time (real) = 0.01 sec\n",
                0,
            )
        else:
            stdout, exit_code = (
                "1/1 Test #7: unit_case ................ ***Failed  0.01 sec\n"
                "0% tests passed, 1 tests failed out of 1\n",
                1,
            )
    report = {
        "queue_id": queue,
        "repo_family": repo,
        "cwd": checkout,
        "command": command,
        "command_text": " ".join(command),
        "log_path": "command_logs/selected.json",
        "stdout_tail": stdout,
        "stderr_tail": "",
        "exit_code": exit_code,
        "timeout": False,
    }
    result = {
        "queue_id": queue,
        "repo_family": repo,
        "checkout_path": checkout,
        "commit_sha": commit,
        "command_attempted": report["command_text"],
        "command_log": report["log_path"],
        "selected_test_ids": selected,
        "exit_code": exit_code,
        "timeout": False,
        "admissible_for_training": False,
    }
    commit_record = {
        "queue_id": queue,
        "repo_family": repo,
        "cwd": checkout,
        "command": ["git", "rev-parse", "HEAD"],
        "stdout_tail": commit + "\n",
        "exit_code": 0,
        "timeout": False,
        "log_path": "command_logs/commit.json",
    }
    smoke = {
        "queue_id": queue,
        "repo_family": repo,
        "checkout_path": checkout,
        "commit_sha": commit,
        "commands_attempted": [{
            "command": ["git", "rev-parse", "HEAD"],
            "log_path": commit_record["log_path"],
            "exit_code": 0,
            "timeout": False,
        }],
    }
    candidate_ref = "candidate-ref"
    source = {
        "source_stage": "stage12125_exact_selected_test_refinement",
        "actual_verifier_command_output_observation_provenance": True,
        "hydratable_verifier_observation_candidate": True,
        "stage12534_constraint_preflight_passed": True,
        "source_lineage_checked": True,
        "controlled_fixture_like": False,
        "generic_selected_test_collapsed": False,
        "candidate_ref_hash": candidate_ref,
        "verifier_exit_status_class": (
            "exit_zero" if exit_code == 0 else "exit_nonzero"
        ),
        "verifier_stdout_hash": sha256(stdout.encode()),
        "verifier_stderr_hash": sha256(b""),
        "training_allowed": False,
        "strict_eval_eligible": False,
    }
    raws = {
        "source": raw(source),
        "result": raw(result),
        "report": raw(report),
        "commit": raw(commit_record),
        "smoke": raw(smoke),
    }
    join = {
        "queue_id": queue,
        "repo_family": repo,
        "checkout_path": checkout,
        "commit_sha": commit,
        "command": command,
        "selected_test_ids": selected,
        "report_sha256": sha256(raws["report"]),
        "result_sha256": sha256(raws["result"]),
        "stage12537_record_sha256": sha256(raws["source"]),
        "smoke_record_sha256": sha256(raws["smoke"]),
        "commit_record_sha256": sha256(raws["commit"]),
        "candidate_ref_hash": candidate_ref,
        "process_exit_code": exit_code,
        "session_exit_code": exit_code,
        "timeout": False,
    }
    raws["join"] = raw(join)
    return {
        "stage12537": source,
        "result": result,
        "report": report,
        "commit_record": commit_record,
        "smoke_record": smoke,
        "join_record": join,
        "raw_stage12537_bytes": raws["source"],
        "raw_result_bytes": raws["result"],
        "raw_report_bytes": raws["report"],
        "raw_commit_bytes": raws["commit"],
        "raw_smoke_bytes": raws["smoke"],
        "raw_join_bytes": raws["join"],
    }


def build_verifier(fixture: dict[str, object]) -> dict:
    return stage.build_observed_verifier_candidate(**fixture)


def reseal_record(fixture: dict[str, object], name: str) -> None:
    raw_names = {
        "stage12537": "raw_stage12537_bytes",
        "result": "raw_result_bytes",
        "report": "raw_report_bytes",
        "commit_record": "raw_commit_bytes",
        "smoke_record": "raw_smoke_bytes",
        "join_record": "raw_join_bytes",
    }
    fixture[raw_names[name]] = raw(fixture[name])


def test_git_metadata_recomputed_from_canonical_evidence() -> None:
    record, objects, roots, entries = git_fixture()
    rows = stage.build_git_metadata_candidates(
        record,
        canonical_tree_objects=objects, canonical_tree_entries=entries,
        canonical_root_commit_oids=roots,
        raw_source_record_bytes=raw(record),
    )
    assert [row["target"] for row in rows] == [
        {"classification_field": "repository_structure", "class": "multi_area"},
        {"classification_field": "test_layout_convention", "class": "none_observed"},
        {"classification_field": "documentation_layout_convention",
         "class": "dedicated_directory"},
    ]
    assert len({row["input_text"] for row in rows}) == 3
    assert all(row["authority"] == stage.AUTHORITY for row in rows)


def _rows_by_metadata_field(rows: list[dict]) -> dict[str, dict]:
    return {row["target"]["classification_field"]: row for row in rows}


def test_git_metadata_inputs_are_visible_layout_not_hidden_counts() -> None:
    record, objects, roots, entries = git_fixture()
    rows = stage.build_git_metadata_candidates(
        record, canonical_tree_objects=objects, canonical_tree_entries=entries,
        canonical_root_commit_oids=roots, raw_source_record_bytes=raw(record),
    )
    for row in rows:
        evidence = json.loads(row["input_text"].split("evidence: ", 1)[1])
        assert set(evidence) == {
            "classification_field", "representative_paths", "file_suffixes",
            "complete_layout_observations",
        }
        assert evidence["representative_paths"] == [
            "docs/readme.md", "src/value.py", "vendor/library",
        ]
        assert "root_count" not in evidence
        assert "tree_object_count" not in evidence
        assert "tree_object_type_counts" not in evidence
        assert row["proof"]["canonical_tree_object_count"] == len(objects)
        assert row["proof"]["canonical_root_commit_oids"] == roots


def test_git_metadata_hidden_history_does_not_change_layout_labels() -> None:
    record, objects, roots, entries = git_fixture()
    baseline = _rows_by_metadata_field(stage.build_git_metadata_candidates(
        record, canonical_tree_objects=objects, canonical_tree_entries=entries,
        canonical_root_commit_oids=roots, raw_source_record_bytes=raw(record),
    ))
    changed = dict(record)
    changed_roots = ["4" * 40, "a" * 40]
    changed["root_commit_git_oids"] = changed_roots
    head_oid = changed["head_commit_git_oid"]
    lineage = [
        f"head:{head_oid}",
        *(f"root:{oid}" for oid in changed_roots),
        *(f"tree:{oid}" for oid in changed["tree_git_oids"]),
    ]
    changed["hard_grouping_key_sha256s"] = [
        sha256(value.encode()) for value in sorted(set(lineage))
    ]
    changed_rows = _rows_by_metadata_field(stage.build_git_metadata_candidates(
        changed, canonical_tree_objects=objects, canonical_tree_entries=entries,
        canonical_root_commit_oids=changed_roots,
        raw_source_record_bytes=raw(changed),
    ))
    assert [row["input_text"] for row in baseline.values()] == [
        row["input_text"] for row in changed_rows.values()
    ]
    assert [row["target"] for row in baseline.values()] == [
        row["target"] for row in changed_rows.values()
    ]


def test_git_metadata_rejects_digest_sorted_lineage_commitment() -> None:
    record, objects, roots, entries = git_fixture()
    authoritative = record["hard_grouping_key_sha256s"]
    reordered = sorted(authoritative)
    assert authoritative != reordered

    record["hard_grouping_key_sha256s"] = reordered
    with pytest.raises(stage.Stage12695Error, match="hard_grouping_commitment_mismatch"):
        stage.build_git_metadata_candidates(
            record, canonical_tree_objects=objects, canonical_tree_entries=entries,
            canonical_root_commit_oids=roots, raw_source_record_bytes=raw(record),
        )


def test_git_metadata_visible_layout_changes_semantic_labels() -> None:
    record, objects, roots, entries = git_fixture()
    baseline = _rows_by_metadata_field(stage.build_git_metadata_candidates(
        record, canonical_tree_objects=objects, canonical_tree_entries=entries,
        canonical_root_commit_oids=roots, raw_source_record_bytes=raw(record),
    ))
    changed_entries = [list(entry) for entry in entries]
    changed_entries[0][4] = "README.md"
    changed_entries[1][4] = "tests/test_value.py"
    changed_entries.sort()
    changed = _rows_by_metadata_field(stage.build_git_metadata_candidates(
        record, canonical_tree_objects=objects,
        canonical_tree_entries=changed_entries, canonical_root_commit_oids=roots,
        raw_source_record_bytes=raw(record),
    ))
    assert changed["test_layout_convention"]["target"]["class"] == "dedicated_top_level"
    assert changed["documentation_layout_convention"]["target"]["class"] == "root_only"
    assert baseline["test_layout_convention"]["input_text"] != (
        changed["test_layout_convention"]["input_text"]
    )


def test_git_metadata_labels_scan_complete_inventory_beyond_encoder_cap() -> None:
    record, _objects, roots, _entries = git_fixture()
    paths = [f"area{index:04d}/file.py" for index in range(520)]
    paths.extend(["readme.md", "tests/test_late.py"])
    objects = [
        ["blob", f"{index + 1:040x}", 10]
        for index in range(len(paths))
    ]
    entries = sorted([
        [record["git_tree_oid"], "100644", "blob", objects[index][1], path]
        for index, path in enumerate(paths)
    ])
    changed = dict(record)
    changed["all_tree_object_count"] = len(objects)
    changed["tree_object_type_counts"] = {"blob": len(objects)}
    changed["all_tree_object_identity_inventory_sha256"] = stage._stable(objects)
    rows = _rows_by_metadata_field(stage.build_git_metadata_candidates(
        changed, canonical_tree_objects=objects, canonical_tree_entries=entries,
        canonical_root_commit_oids=roots, raw_source_record_bytes=raw(changed),
    ))
    test_row = rows["test_layout_convention"]
    doc_row = rows["documentation_layout_convention"]
    assert test_row["target"]["class"] == "dedicated_top_level"
    assert doc_row["target"]["class"] == "root_only"
    evidence = json.loads(test_row["input_text"].split("evidence: ", 1)[1])
    assert len(evidence["representative_paths"]) == 512
    assert "tests/test_late.py" in evidence["representative_paths"]
    assert "readme.md" in evidence["representative_paths"]
    assert evidence["complete_layout_observations"][
        "complete_authenticated_inventory_scanned"
    ] is True


def test_git_metadata_rejects_layout_object_inventory_mismatch() -> None:
    record, objects, roots, entries = git_fixture()
    with pytest.raises(
        stage.Stage12695Error, match="tree_layout_object_inventory_mismatch",
    ):
        stage.build_git_metadata_candidates(
            record, canonical_tree_objects=objects[:-1],
            canonical_tree_entries=entries, canonical_root_commit_oids=roots,
            raw_source_record_bytes=raw(record),
        )


def test_canonical_tree_layout_accepts_exact_safe_unicode_paths() -> None:
    tree_oid = "1" * 40
    object_oid = "2" * 40
    paths = ["src/caf\u00e9.py", "docs/\u65e5\u672c\u8a9e/readme.md", "src/e\u0301.py"]
    entries = [
        [tree_oid, "100644", "blob", object_oid, path]
        for path in sorted(paths)
    ]

    canonical, fields = stage._canonical_tree_layout(entries)

    assert [entry[4] for entry in canonical] == sorted(paths)
    assert set(fields["representative_paths"]) == set(paths)


@pytest.mark.parametrize(
    "path",
    [
        "/absolute.py", "trailing/", "repeated//separator.py", "./dot.py",
        "parent/../escape.py", "back\\slash.py", "nul\x00byte.py",
        "format\u200bmark.py", "private\ue000use.py", "surrogate\ud800.py",
        "unassigned\u0378.py",
    ],
)
def test_canonical_tree_layout_rejects_noncanonical_or_unsafe_unicode_paths(
    path: str,
) -> None:
    with pytest.raises(stage.Stage12695Error, match="invalid_canonical_tree_entry_path"):
        stage._canonical_tree_layout(
            [["1" * 40, "100644", "blob", "2" * 40, path]]
        )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("all_tree_object_count", 999, "catalog_tree_object_count_mismatch"),
        ("tree_object_type_counts", {"blob": 3}, "catalog_tree_object_type_counts_mismatch"),
        ("all_tree_object_identity_inventory_sha256", "0" * 64,
         "catalog_tree_object_inventory_mismatch"),
        ("hard_grouping_key_sha256s", [], "hard_grouping_commitment_mismatch"),
    ],
)
def test_git_metadata_rejects_resealed_forge(
    field: str, value: object, reason: str
) -> None:
    record, objects, roots, entries = git_fixture()
    record[field] = value
    with pytest.raises(stage.Stage12695Error, match=reason):
        stage.build_git_metadata_candidates(
            record,
            canonical_tree_objects=objects, canonical_tree_entries=entries,
            canonical_root_commit_oids=roots,
            raw_source_record_bytes=raw(record),
        )


def test_git_metadata_requires_external_canonical_evidence() -> None:
    record, _objects, _roots, _entries = git_fixture()
    with pytest.raises(stage.EvidenceUnavailable, match="canonical_git_evidence"):
        stage.build_git_metadata_candidates(record, raw_source_record_bytes=raw(record))


def test_git_metadata_rejects_root_and_revision_forgery() -> None:
    record, objects, roots, entries = git_fixture()
    with pytest.raises(stage.Stage12695Error, match="catalog_lineage_inventory_mismatch"):
        stage.build_git_metadata_candidates(
            record,
            canonical_tree_objects=objects, canonical_tree_entries=entries,
            canonical_root_commit_oids=["0" * 40],
            raw_source_record_bytes=raw(record),
        )
    record["revision"] = "0" * 40
    with pytest.raises(stage.Stage12695Error, match="revision_head_mismatch"):
        stage.build_git_metadata_candidates(
            record,
            canonical_tree_objects=objects, canonical_tree_entries=entries,
            canonical_root_commit_oids=roots,
            raw_source_record_bytes=raw(record),
        )


def test_scalar_declaration_binds_exact_source_and_span() -> None:
    row, source = scalar_declaration_fixture()
    candidate = stage.build_parsed_declaration_metadata_candidate(
        row,
        canonical_source_bytes=source,
        raw_source_record_bytes=raw(row),
    )
    assert candidate["target"]["class"] == "python_toml_literal_scalar"
    assert "demo" not in candidate["input_text"]
    assert "<SCALAR>" in candidate["input_text"]
    assert {
        key: candidate["proof"][key]
        for key in (
            "repository_key_sha256", "content_component_sha256",
            "revision", "source_path",
        )
    } == {
        "repository_key_sha256": "a" * 64,
        "content_component_sha256": "b" * 64,
        "revision": "c" * 40,
        "source_path": "pyproject.toml",
    }


def test_reference_declaration_binds_definition_and_candidate() -> None:
    row, source = reference_declaration_fixture()
    candidate = stage.build_parsed_declaration_metadata_candidate(
        row,
        canonical_source_bytes=source,
        raw_source_record_bytes=raw(row),
    )
    assert candidate["target"]["class"] == "npm_literal_script_reference"
    assert candidate["proof"]["selected_literal_sha256"] == sha256(b"lint")


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("source", "canonical_source_sha256_mismatch"),
        ("target", "selected_literal_target_mismatch"),
        ("span", "selected_literal_target_mismatch"),
        ("blob", "canonical_source_git_blob_mismatch"),
    ],
)
def test_declaration_rejects_resealed_source_or_span_forgery(
    mutation: str, reason: str
) -> None:
    row, source = scalar_declaration_fixture()
    if mutation == "source":
        source = source.replace(b"demo", b"prod")
    elif mutation == "target":
        row["target"]["decoder_text"] = "prod"
    elif mutation == "span":
        row["source_provenance"]["target_start_byte"] += 1
    else:
        row["source_provenance"]["source_git_blob_oid"] = "0" * 40
    with pytest.raises(stage.Stage12695Error, match=reason):
        stage.build_parsed_declaration_metadata_candidate(
            row,
            canonical_source_bytes=source,
            raw_source_record_bytes=raw(row),
        )


def test_target_mutation_does_not_create_oracle_input_channel() -> None:
    first_row, first_source = scalar_declaration_fixture("demo")
    second_row, second_source = scalar_declaration_fixture("prod")
    first = stage.build_parsed_declaration_metadata_candidate(
        first_row, canonical_source_bytes=first_source,
        raw_source_record_bytes=raw(first_row)
    )
    second = stage.build_parsed_declaration_metadata_candidate(
        second_row, canonical_source_bytes=second_source,
        raw_source_record_bytes=raw(second_row)
    )
    assert first["input_text"] == second["input_text"]
    assert "demo" not in first["input_text"]
    assert "prod" not in second["input_text"]
    with pytest.raises(stage.Stage12695Error, match="forbidden_encoder_input_field"):
        stage._render_input("x", {"target_label": "oracle"}, ("target_label",))


@pytest.mark.parametrize(
    ("command", "stdout", "outcome"),
    [
        (["pytest", "tests/test_x.py"], "2 passed, 1 skipped in 0.10s\n", "observed_pass"),
        (["pytest", "tests/test_x.py"], "1 failed in 0.10s\n", "test_failure"),
        (["pytest", "tests/test_x.py"], "1 error in 0.10s\n",
         "environment_or_setup_failure"),
    ],
)
def test_pytest_complete_terminal_parsing(
    command: list[str], stdout: str, outcome: str
) -> None:
    assert stage.parse_observed_test_report(command, stdout, "")["outcome_class"] == outcome


@pytest.mark.parametrize(
    "stdout",
    [
        "10 tests collected in 0.01s\n",
        "1 passed, 2 passed in 0.01s\n",
        "collected 1 item\n",
    ],
)
def test_pytest_collection_or_noncanonical_summary_rejected(stdout: str) -> None:
    with pytest.raises(stage.Stage12695Error):
        stage.parse_observed_test_report(["pytest", "tests/test_x.py"], stdout, "")


def test_ctest_complete_terminal_parsing() -> None:
    fixture = verifier_fixture("ctest", "pass")
    parsed = stage.parse_observed_test_report(
        fixture["report"]["command"],
        fixture["report"]["stdout_tail"],
        "",
    )
    assert parsed["counts"]["passed"] == 1
    assert parsed["outcome_class"] == "observed_pass"


def test_ctest_duplicate_result_identity_rejected() -> None:
    stdout = (
        "1/2 Test #7: first ................ Passed  0.01 sec\n"
        "2/2 Test #7: duplicate ............ Passed  0.01 sec\n"
        "100% tests passed, 0 tests failed out of 2\n"
    )
    with pytest.raises(stage.Stage12695Error, match="ctest_result_identity_or_count_mismatch"):
        stage.parse_observed_test_report(["ctest"], stdout, "")


@pytest.mark.parametrize(
    ("family", "outcome", "expected"),
    [
        ("pytest", "pass", "observed_pass"),
        ("pytest", "fail", "test_failure"),
        ("pytest", "error", "environment_or_setup_failure"),
        ("ctest", "pass", "observed_pass"),
        ("ctest", "fail", "test_failure"),
    ],
)
def test_complete_verifier_join_happy_paths(
    family: str, outcome: str, expected: str
) -> None:
    candidate = build_verifier(verifier_fixture(family, outcome))
    assert candidate["target"]["outcome_class"] == expected
    assert candidate["target"]["scope"] == "selected_tests_only"
    assert candidate["authority"] == stage.AUTHORITY


@pytest.mark.parametrize(
    ("record_name", "field", "value", "reason"),
    [
        ("result", "queue_id", "forged", "queue_or_repository_join_mismatch"),
        ("report", "repo_family", "forged", "queue_or_repository_join_mismatch"),
        ("report", "cwd", "/tmp/other", "checkout_path_join_mismatch"),
        ("smoke_record", "commit_sha", "0" * 40, "commit_join_mismatch"),
        ("commit_record", "stdout_tail", "0" * 40 + "\n", "commit_command_output_invalid"),
        ("report", "timeout", True, "explicit_join_commitment_mismatch"),
        ("report", "exit_code", 9, "explicit_join_commitment_mismatch"),
    ],
)
def test_verifier_join_rejects_resealed_link_mutation(
    record_name: str, field: str, value: object, reason: str
) -> None:
    fixture = verifier_fixture()
    fixture[record_name][field] = value
    reseal_record(fixture, record_name)
    with pytest.raises(stage.Stage12695Error, match=reason):
        build_verifier(fixture)


def test_verifier_requires_authenticated_join_record() -> None:
    fixture = verifier_fixture()
    fixture["join_record"] = None
    fixture["raw_join_bytes"] = None
    with pytest.raises(stage.EvidenceUnavailable, match="join_unavailable"):
        build_verifier(fixture)


def test_verifier_selected_scope_is_exactly_bound() -> None:
    fixture = verifier_fixture()
    fixture["result"]["selected_test_ids"] = ["tests/other.py::test_ok"]
    reseal_record(fixture, "result")
    with pytest.raises(stage.Stage12695Error, match="pytest_selected_scope_not_bound"):
        build_verifier(fixture)


def test_ctest_scope_allows_safe_hyphen_literal_but_not_regex_metacharacters() -> None:
    stage._validate_selected_scope(
        ["ctest", "-R", "^test-cpp17$"], ["test-cpp17"],
    )
    stage._validate_selected_scope(
        ["ctest", "-R", r"^test\.cpp$"], ["test.cpp"],
    )
    with pytest.raises(stage.Stage12695Error, match="ctest_selected_scope_not_bound"):
        stage._validate_selected_scope(
            ["ctest", "-R", "^test.cpp$"], ["test.cpp"],
        )


@pytest.mark.parametrize("record_name", ["report", "result"])
def test_verifier_fully_resealed_timeout_is_ineligible(record_name: str) -> None:
    fixture = verifier_fixture()
    fixture[record_name]["timeout"] = True
    reseal_record(fixture, record_name)
    commitment = "report_sha256" if record_name == "report" else "result_sha256"
    fixture["join_record"][commitment] = sha256(
        fixture["raw_report_bytes"]
        if record_name == "report"
        else fixture["raw_result_bytes"]
    )
    reseal_record(fixture, "join_record")
    with pytest.raises(stage.Stage12695Error, match="timed_out_report_ineligible"):
        build_verifier(fixture)


def test_verifier_process_session_exit_join_is_fail_closed() -> None:
    fixture = verifier_fixture()
    fixture["join_record"]["session_exit_code"] = 9
    reseal_record(fixture, "join_record")
    with pytest.raises(
        stage.Stage12695Error, match="process_session_timeout_join_mismatch"
    ):
        build_verifier(fixture)


def candidate(input_text: str, target: str) -> dict:
    return {
        "input_text": input_text,
        "target": {"decoder_text": target},
        "proof": {},
        "authority": dict(stage.AUTHORITY),
    }


def test_global_dedup_collapses_exact_input_target_duplicates() -> None:
    retained, counts = stage.deduplicate_candidates([
        candidate("input-a", "target-a"),
        candidate("input-a", "target-a"),
        candidate("input-b", "target-b"),
    ])
    assert len(retained) == 2
    assert counts == {
        "raw_candidate_rows": 3,
        "unique_candidate_rows": 2,
        "duplicate_or_conflicting_rows_quarantined": 1,
        "conflicting_encoder_inputs": 0,
    }
    assert len({
        row["proof"]["dedup_model_example_sha256"] for row in retained
    }) == 2


def test_global_dedup_quarantines_conflicting_input_targets() -> None:
    retained, counts = stage.deduplicate_candidates([
        candidate("same-input", "first"),
        candidate("same-input", "second"),
        candidate("kept", "only"),
    ])
    assert [row["input_text"] for row in retained] == ["kept"]
    assert counts["conflicting_encoder_inputs"] == 1
    assert counts["duplicate_or_conflicting_rows_quarantined"] == 2


def test_global_dedup_rejects_open_authority() -> None:
    row = candidate("input", "target")
    row["authority"]["training_admitted"] = True
    with pytest.raises(stage.Stage12695Error, match="source_authority_not_closed"):
        stage.deduplicate_candidates([row])


def test_actual_accepted_inventory_reports_honest_zero_validated_supply() -> None:
    inventory = stage.discover_source_counts()
    assert inventory["source_counts"] == {
        "stage12688_catalog_records": 479,
        "stage12692_parser_backed_rows": 1692,
        "stage12537_provenance_candidates": 13,
        "stage12537_candidates_grounded_in_stage12125": 3,
        "stage12125_selected_test_results": 3,
        "stage12123_smoke_results": 12,
    }
    assert inventory["legacy_unvalidated_projection_probe"] == {
        "raw_projection_rows": 3132,
        "unique_encoder_inputs": 1329,
        "duplicate_encoder_input_rows": 1803,
        "counted_as_validated_supply": False,
    }
    assert inventory["validated_unique_supply"]["total_rows"] == 0
    assert inventory["quarantine"]["total_quarantined_raw_projection_rows"] == 3132
    assert inventory["full_materialization_performed"] is False
    assert inventory["publication_performed"] is False


def test_all_authority_and_admission_fields_remain_false() -> None:
    inventory = stage.discover_source_counts()
    assert inventory["authority"] == stage.AUTHORITY
    assert not any(inventory["authority"].values())
    assert inventory["global_split_dependency"]["satisfied"] is False
    record, objects, roots, entries = git_fixture()
    rows = stage.build_git_metadata_candidates(
        record,
        canonical_tree_objects=objects, canonical_tree_entries=entries,
        canonical_root_commit_oids=roots,
        raw_source_record_bytes=raw(record),
    )
    assert all(not any(row["authority"].values()) for row in rows)


def test_source_authority_true_is_rejected() -> None:
    row, source = scalar_declaration_fixture()
    row["authority"]["training_admitted"] = True
    with pytest.raises(stage.Stage12695Error, match="source_authority_not_closed"):
        stage.build_parsed_declaration_metadata_candidate(
            row, canonical_source_bytes=source, raw_source_record_bytes=raw(row)
        )


def test_main_requires_inventory_only(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(stage.Stage12695Error, match="requires_inventory_only"):
        stage.main([])
    assert stage.main(["--inventory-only"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["validated_unique_supply"]["total_rows"] == 0
