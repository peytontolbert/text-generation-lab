from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12692_source_backed_declarative_test_build_conventions.py"
SPEC = importlib.util.spec_from_file_location("stage12692_package_json", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage
SPEC.loader.exec_module(stage)

REPO_KEY = "a" * 64
REVISION = "b" * 40
BLOB = "c" * 40


def extract(source: str, **kwargs):
    return stage.extract_package_json_rows(
        source.encode("utf-8"),
        repository_key_sha256=REPO_KEY,
        revision=REVISION,
        package_blob_oid=BLOB,
        **kwargs,
    )


def fixture() -> str:
    return """{
  "name": "fixture",
  "scripts": {
    "build": "tsc",
    "lint": "eslint .",
    "test": "pytest tests",
    "docs": "sphinx-build docs out",
    "ci": "npm run test",
    "check": "yarn run lint",
    "release": "pnpm run build"
  }
}"""


def invocation(row):
    return row["input_text"].split("invocation: ", 1)[1].split("\n", 1)[0]


def test_literal_managers_create_exact_rows_with_false_authority():
    rows = extract(fixture())
    assert len(rows) == 3
    assert {r["target"]["decoder_text"] for r in rows}
    for row in rows:
        assert row["ecosystem"] == "npm"
        assert row["objective_family"] == stage.OBJECTIVE_FAMILY
        assert row["loss_mask"] == {"decoder_ce": True}
        assert all(value is False for value in row["authority"].values())
        assert row["input_text"].count("<TARGET>") == 1
        assert "candidate_0:" in row["input_text"]
        assert "candidate_3:" in row["input_text"]


def test_utf8_byte_spans_reconstruct_reference_and_definition():
    source = fixture().replace('"name": "fixture"', '"name": "caf\u00e9"')
    source_bytes = source.encode("utf-8")
    row = next(r for r in extract(source) if '"ci": "npm run <TARGET>"' in r["input_text"])
    proof = row["source_provenance"]
    assert source_bytes[
        proof["reference_target_start_byte"]:proof["reference_target_end_byte"]
    ] == b"test"
    assert source_bytes[
        proof["definition_name_start_byte"]:proof["definition_name_end_byte"]
    ] == b"test"
    assert source_bytes[
        proof["definition_command_start_byte"]:proof["definition_command_end_byte"]
    ] == b"pytest tests"


def test_candidate_order_is_deterministic_and_reference_target_independent():
    rows = extract(fixture())
    candidate_blocks = [
        row["input_text"].split("candidates:\n", 1)[1] for row in rows
    ]
    assert len(set(candidate_blocks)) == 1
    assert rows == extract(fixture())


def test_mutating_decoder_target_cannot_mutate_encoder_input():
    row = extract(fixture())[0]
    before = row["input_text"]
    row["target"]["decoder_text"] = "candidate_999"
    assert row["input_text"] == before
    assert "candidate_999" not in row["input_text"]


def test_requires_four_candidates_and_caps_at_eight():
    assert extract('{"scripts":{"a":"a","b":"b","c":"npm run a"}}') == []
    definitions = ",".join(f'"s{i}":"command{i}"' for i in range(8))
    source = '{"scripts":{' + definitions + ',"invoke":"npm run s0"}}'
    parsed = stage.parse_package_json_scripts(source.encode("utf-8"))
    assert len(stage.deterministic_candidates(parsed)) == 8
    rows = extract(source)
    assert len(rows) == 1
    block = rows[0]["input_text"].split("candidates:\n", 1)[1]
    assert len(block.splitlines()) == 8


@pytest.mark.parametrize("command", [
    "npm run $TARGET",
    "npm run ${TARGET}",
    "npm run test && npm run lint",
    "npm run test || true",
    "npm run test; echo done",
    "npm run test -- --watch",
    "npx npm run test",
    "npm test",
    "yarn test",
])
def test_dynamic_ambiguous_and_noncanonical_commands_are_rejected(command):
    source = fixture().replace("npm run test", command)
    assert not any('"ci":' in invocation(row) for row in extract(source))


def test_alias_targets_are_rejected():
    source = """{"scripts":{
      "unit":"pytest", "test":"npm run unit", "lint":"eslint .",
      "build":"tsc", "ci":"npm run test"
    }}"""
    assert not any('"ci":' in invocation(row) for row in extract(source))


def test_missing_and_unselected_targets_are_rejected():
    missing = fixture().replace("npm run test", "npm run absent")
    assert not any('"ci":' in invocation(row) for row in extract(missing))

    definitions = ",".join(f'"s{i}":"command{i}"' for i in range(12))
    source = '{"scripts":{' + definitions + ',"invoke":"npm run absent"}}'
    assert extract(source) == []


def test_duplicate_and_nonstring_definitions_fail_closed():
    with pytest.raises(stage.PackageJsonError, match="duplicate_json_key"):
        extract('{"scripts":{"test":"a","test":"b","x":"x","y":"y","z":"z"}}')
    with pytest.raises(stage.PackageJsonError, match="script_definition_not_string"):
        extract('{"scripts":{"test":["pytest"],"x":"x","y":"y","z":"z"}}')


def test_escaped_script_spans_are_conservatively_rejected():
    with pytest.raises(stage.PackageJsonError, match="escaped_script_definition_unsupported"):
        extract('{"scripts":{"te\\u0073t":"pytest","a":"a","b":"b","c":"npm run test"}}')
    with pytest.raises(stage.PackageJsonError, match="escaped_script_definition_unsupported"):
        extract('{"scripts":{"test":"py\\u0074est","a":"a","b":"b","c":"npm run test"}}')


@pytest.mark.parametrize("source", [
    b"not json",
    b"[]",
    b'{"scripts":[]}',
    b'{"scripts":{"a":"x"}} trailing',
    b'{"scripts":{"a":"\xff"}}',
])
def test_invalid_structures_fail_closed(source):
    with pytest.raises(stage.PackageJsonError):
        stage.parse_package_json_scripts(source)


@pytest.mark.parametrize("path", [
    "/package.json",
    "../package.json",
    "a//package.json",
    "a\\package.json",
])
def test_path_must_be_canonical_relative(path):
    with pytest.raises(ValueError, match="package_path_not_canonical_relative"):
        extract(fixture(), package_path=path)


def test_provenance_and_identity_are_source_bound():
    first = extract(fixture())[0]
    changed = extract(fixture().replace("pytest tests", "pytest -q"))[0]
    assert first["row_id"] != changed["row_id"]
    assert first["source_provenance"]["package_file_sha256"] != changed[
        "source_provenance"
    ]["package_file_sha256"]
    assert first["source_provenance"]["parser_adapter"] == stage.PARSER_ADAPTER
    assert first["source_provenance"]["proof_contract"] == stage.PROOF_CONTRACT


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_constants_fail_in_both_json_parsers(constant):
    source = ('{"metadata":' + constant + ',"scripts":{"a":"a","b":"b","c":"c","d":"d"}}').encode("utf-8")
    with pytest.raises(stage.PackageJsonError, match="non_finite_json_constant"):
        stage._stdlib_unique(source)
    with pytest.raises(stage.PackageJsonError, match="non_finite_json_constant"):
        stage._SpanParser(source).parse()
    with pytest.raises(stage.PackageJsonError, match="non_finite_json_constant"):
        stage.parse_package_json_scripts(source)


def test_forwarded_and_compound_aliases_never_enter_candidates():
    source = """{"scripts":{
      "build":"tsc",
      "lint":"eslint .",
      "test":"pytest",
      "docs":"sphinx-build docs out",
      "forwarded":"npm run test -- --watch",
      "compound":"pnpm run lint && npm run test",
      "ci":"yarn run test"
    }}"""
    rows = extract(source)
    assert len(rows) == 1
    block = rows[0]["input_text"].split("candidates:\n", 1)[1]
    assert '"forwarded"' not in block
    assert '"compound"' not in block
    assert '"ci"' not in block
    assert len(block.splitlines()) == 4


def test_rebuild_after_reference_target_mutation_preserves_input_and_changes_label():
    first_source = """{"scripts":{
      "build":"tsc","lint":"eslint .","test":"pytest","docs":"sphinx",
      "ci":"npm run test"
    }}"""
    second_source = first_source.replace("npm run test", "npm run lint")
    first = extract(first_source)[0]
    second = extract(second_source)[0]
    assert first["input_text"] == second["input_text"]
    assert first["target"]["decoder_text"] != second["target"]["decoder_text"]
    assert first["row_id"] != second["row_id"]


def test_all_source_spans_and_hash_reconstruct_for_emitted_row():
    import hashlib

    source = fixture().encode("utf-8")
    row = next(r for r in extract(fixture()) if '"ci": "npm run <TARGET>"' in r["input_text"])
    proof = row["source_provenance"]
    expected = {
        ("invocation_name_start_byte", "invocation_name_end_byte"): b"ci",
        ("invocation_command_start_byte", "invocation_command_end_byte"): b"npm run test",
        ("reference_target_start_byte", "reference_target_end_byte"): b"test",
        ("definition_name_start_byte", "definition_name_end_byte"): b"test",
        ("definition_command_start_byte", "definition_command_end_byte"): b"pytest tests",
    }
    for (start_key, end_key), exact in expected.items():
        assert source[proof[start_key]:proof[end_key]] == exact
    assert proof["package_file_sha256"] == hashlib.sha256(source).hexdigest()


def test_identity_binds_repo_revision_blob_and_path():
    source = fixture()
    base = extract(source)[0]
    mutations = [
        stage.extract_package_json_rows(
            source.encode("utf-8"),
            repository_key_sha256="d" * 64,
            revision=REVISION,
            package_blob_oid=BLOB,
        )[0],
        stage.extract_package_json_rows(
            source.encode("utf-8"),
            repository_key_sha256=REPO_KEY,
            revision="e" * 40,
            package_blob_oid=BLOB,
        )[0],
        stage.extract_package_json_rows(
            source.encode("utf-8"),
            repository_key_sha256=REPO_KEY,
            revision=REVISION,
            package_blob_oid="f" * 40,
        )[0],
        extract(source, package_path="packages/tool/package.json")[0],
    ]
    assert len({base["row_id"], *(row["row_id"] for row in mutations)}) == 5


def test_escaped_and_literal_equivalent_keys_are_duplicates_in_both_parsers():
    source = b'{"scripts":{"test":"a","te\\u0073t":"b","x":"x","y":"y","z":"z"}}'
    with pytest.raises(stage.PackageJsonError, match="duplicate_json_key"):
        stage._stdlib_unique(source)
    with pytest.raises(stage.PackageJsonError, match="duplicate_json_key"):
        stage._SpanParser(source).parse()
    with pytest.raises(stage.PackageJsonError, match="duplicate_json_key"):
        stage.parse_package_json_scripts(source)


def test_multibyte_content_before_every_reconstructed_span():
    source = """{
      "name":"caf\u00e9",
      "scripts":{
        "\u00e9cho":"printf ok",
        "build":"tsc",
        "lint":"eslint .",
        "test":"pytest",
        "ci-\u00e9":"npm run test"
      }
    }"""
    encoded = source.encode("utf-8")
    row = extract(source)[0]
    proof = row["source_provenance"]
    assert encoded[proof["invocation_name_start_byte"]:proof["invocation_name_end_byte"]] == "ci-\u00e9".encode("utf-8")
    assert encoded[proof["invocation_command_start_byte"]:proof["invocation_command_end_byte"]] == b"npm run test"
    assert encoded[proof["reference_target_start_byte"]:proof["reference_target_end_byte"]] == b"test"
    assert encoded[proof["definition_name_start_byte"]:proof["definition_name_end_byte"]] == b"test"
    assert encoded[proof["definition_command_start_byte"]:proof["definition_command_end_byte"]] == b"pytest"


TOX_BLOB = "1" * 40
TOML_BLOB = "2" * 40


def extract_tox(source: str, **kwargs):
    return stage.extract_tox_ini_rows(
        source.encode("utf-8"),
        repository_key_sha256=REPO_KEY,
        revision=REVISION,
        source_blob_oid=TOX_BLOB,
        **kwargs,
    )


def tox_fixture(target: str = "py311") -> str:
    return f"""[tox]
envlist = py311, lint, docs, type

[testenv:py311]
commands = pytest
[testenv:lint]
commands = ruff check .
[testenv:docs]
commands = sphinx-build docs out
[testenv:type]
commands = mypy src

[testenv:ci]
commands = tox -e {target}
"""


def extract_pyproject(source: str, **kwargs):
    return stage.extract_pyproject_toml_rows(
        source.encode("utf-8"),
        repository_key_sha256=REPO_KEY,
        revision=REVISION,
        source_blob_oid=TOML_BLOB,
        **kwargs,
    )


def pyproject_fixture(tool: str = "ruff") -> str:
    return f"""[tool.pytest.ini_options]
testpaths = ["tests", "integration"]
addopts = "-q"

[tool.{tool}]
line-length = 88
"""


def extract_cargo(source: str, **kwargs):
    return stage.extract_cargo_toml_rows(
        source.encode("utf-8"),
        repository_key_sha256=REPO_KEY,
        revision=REVISION,
        source_blob_oid=TOML_BLOB,
        **kwargs,
    )


def cargo_fixture(target: str = "core") -> str:
    return f"""[package]
name = "root"

[workspace]
members = ["core", "cli", "web", "util"]

[workspace.metadata.commands]
check = "cargo -p {target}"
"""


def test_tox_exact_resolution_spans_candidates_and_authority():
    source = tox_fixture()
    encoded = source.encode("utf-8")
    rows = extract_tox(source)
    assert len(rows) == 1
    row = rows[0]
    assert row["ecosystem"] == "tox"
    assert row["input_text"].count("<TARGET>") == 1
    assert len(row["input_text"].split("candidates:\n", 1)[1].splitlines()) == 4
    assert all(value is False for value in row["authority"].values())
    proof = row["source_provenance"]
    assert encoded[
        proof["reference_target_start_byte"]:proof["reference_target_end_byte"]
    ] == b"py311"
    assert encoded[
        proof["definition_start_byte"]:proof["definition_end_byte"]
    ] == b"py311"
    assert proof["source_file_sha256"] == __import__("hashlib").sha256(encoded).hexdigest()


def test_tox_real_target_mutation_preserves_input_and_changes_label():
    first = extract_tox(tox_fixture("py311"))[0]
    second = extract_tox(tox_fixture("lint"))[0]
    assert first["input_text"] == second["input_text"]
    assert first["target"]["decoder_text"] != second["target"]["decoder_text"]


@pytest.mark.parametrize("bad", [
    tox_fixture() + "\n[testenv:lint]\ncommands = other\n",
    tox_fixture().replace("commands = pytest", "commands = %(base)s"),
    tox_fixture().replace("commands = pytest", "commands = ${COMMAND}"),
    tox_fixture().replace("py311, lint", "{py311,py312}, lint"),
])
def test_tox_duplicates_interpolation_and_dynamic_envlists_fail_closed(bad):
    with pytest.raises(stage.PackageJsonError):
        extract_tox(bad)


def test_tox_requires_four_real_same_file_definitions_and_exact_bare_ref():
    three = tox_fixture().replace(
        "[testenv:type]\ncommands = mypy src\n", ""
    ).replace(", type", "")
    assert extract_tox(three) == []
    forwarded = tox_fixture().replace("tox -e py311", "tox -e py311 -- --watch")
    assert extract_tox(forwarded) == []


def test_tox_identity_binds_source_path():
    first = extract_tox(tox_fixture())[0]
    second = extract_tox(tox_fixture(), source_path="config/tox.ini")[0]
    assert first["row_id"] != second["row_id"]


def test_pyproject_emits_only_exact_scalar_completion_rows():
    source = pyproject_fixture()
    encoded = source.encode("utf-8")
    rows = extract_pyproject(source)
    assert len(rows) == 5
    assert {row["objective_family"] for row in rows} == {
        "declarative_test_build_scalar_completion"
    }
    assert {row["target"]["decoder_text"] for row in rows} == {
        "pytest.ini_options", "tests", "integration", "-q", "ruff"
    }
    for row in rows:
        assert "<SCALAR>" in row["input_text"]
        assert all(value is False for value in row["authority"].values())
        proof = row["source_provenance"]
        target = encoded[proof["target_start_byte"]:proof["target_end_byte"]]
        assert target.decode("utf-8") == row["target"]["decoder_text"]


def test_pyproject_tool_mutation_preserves_input_and_changes_exact_target():
    ruff = next(
        row for row in extract_pyproject(pyproject_fixture("ruff"))
        if row["target"]["decoder_text"] == "ruff"
    )
    mypy = next(
        row for row in extract_pyproject(pyproject_fixture("mypy"))
        if row["target"]["decoder_text"] == "mypy"
    )
    assert ruff["input_text"] == mypy["input_text"]
    assert ruff["target"] != mypy["target"]
    assert ruff["row_id"] != mypy["row_id"]


def test_pyproject_rejects_duplicate_escaped_and_multiline_testpaths():
    duplicate = pyproject_fixture().replace(
        '["tests", "integration"]', '["tests", "tests"]'
    )
    escaped = pyproject_fixture().replace(
        '"tests"', '"te\\u0073ts"'
    )
    multiline = pyproject_fixture().replace(
        '["tests", "integration"]', '[\n  "tests",\n  "integration",\n]'
    )
    with pytest.raises(stage.PackageJsonError, match="ambiguous_duplicate_textual_span"):
        extract_pyproject(duplicate)
    with pytest.raises(stage.PackageJsonError, match="escaped_or_dynamic_array_value"):
        extract_pyproject(escaped)
    with pytest.raises(stage.PackageJsonError, match="computed_or_multiline"):
        extract_pyproject(multiline)


def test_pyproject_multibyte_prefix_keeps_exact_byte_spans():
    source = 'project_note = "caf\u00e9"\n\n' + pyproject_fixture()
    encoded = source.encode("utf-8")
    for row in extract_pyproject(source):
        proof = row["source_provenance"]
        assert encoded[
            proof["target_start_byte"]:proof["target_end_byte"]
        ].decode("utf-8") == row["target"]["decoder_text"]


def test_cargo_workspace_members_are_scalar_only_and_resolution_is_unsupported():
    source = cargo_fixture()
    encoded = source.encode("utf-8")
    rows = extract_cargo(source)
    assert stage.CARGO_PACKAGE_RESOLUTION_SUPPORTED is False
    assert len(rows) == 5
    assert {
        row["objective_family"] for row in rows
    } == {"declarative_test_build_scalar_completion"}
    assert {row["target"]["decoder_text"] for row in rows} == {
        "root", "core", "cli", "web", "util"
    }
    for row in rows:
        proof = row["source_provenance"]
        assert encoded[
            proof["target_start_byte"]:proof["target_end_byte"]
        ].decode("utf-8") == row["target"]["decoder_text"]
        assert all(value is False for value in row["authority"].values())


def test_cargo_p_selector_never_creates_resolution_without_child_manifests():
    exact = extract_cargo(cargo_fixture("core"))
    changed = extract_cargo(cargo_fixture("util"))
    dynamic = extract_cargo(
        cargo_fixture().replace("cargo -p core", "cargo -p ${PACKAGE}")
    )
    for rows in (exact, changed, dynamic):
        assert rows
        assert all(
            row["objective_family"]
            == "declarative_test_build_scalar_completion"
            for row in rows
        )


def test_cargo_rejects_duplicate_and_escaped_member_values():
    duplicate = cargo_fixture().replace(
        '["core", "cli", "web", "util"]',
        '["core", "core", "web", "util"]',
    )
    escaped = cargo_fixture().replace('"core"', '"co\\u0072e"', 1)
    with pytest.raises(stage.PackageJsonError, match="ambiguous_duplicate"):
        extract_cargo(duplicate)
    with pytest.raises(stage.PackageJsonError, match="escaped_or_dynamic_array_value"):
        extract_cargo(escaped)


def test_all_new_adapter_rows_bind_repo_revision_blob_and_keep_authority_false():
    cases = [
        (stage.extract_tox_ini_rows, tox_fixture().encode("utf-8"), TOX_BLOB, "tox.ini"),
        (stage.extract_pyproject_toml_rows, pyproject_fixture().encode("utf-8"), TOML_BLOB, "pyproject.toml"),
        (stage.extract_cargo_toml_rows, cargo_fixture().encode("utf-8"), TOML_BLOB, "Cargo.toml"),
    ]
    for function, source, blob, path in cases:
        base = function(
            source,
            repository_key_sha256=REPO_KEY,
            revision=REVISION,
            source_blob_oid=blob,
            source_path=path,
        )
        changed = function(
            source,
            repository_key_sha256="d" * 64,
            revision="e" * 40,
            source_blob_oid="f" * 40,
            source_path="nested/" + path,
        )
        assert base
        assert {row["row_id"] for row in base}.isdisjoint(
            row["row_id"] for row in changed
        )
        assert all(
            all(value is False for value in row["authority"].values())
            for row in base + changed
        )


def test_tox_multiline_envlist_and_commands_keep_exact_spans():
    source = tox_fixture().replace(
        "envlist = py311, lint, docs, type",
        "envlist =\n    py311,\n    lint,\n    docs,\n    type",
    ).replace(
        "commands = tox -e py311",
        "commands =\n    tox -e py311",
    )
    encoded = source.encode("utf-8")
    row = extract_tox(source)[0]
    proof = row["source_provenance"]
    assert encoded[
        proof["reference_target_start_byte"]:proof["reference_target_end_byte"]
    ] == b"py311"


def test_nested_pyproject_tool_paths_are_distinct_exact_scalars():
    source = pyproject_fixture() + """
[tool.ruff.lint]
select = ["E"]
"""
    targets = [
        row["target"]["decoder_text"]
        for row in extract_pyproject(source)
        if row["source_provenance"]["parser_adapter"]["name"]
        == "stdlib_tomllib_pyproject"
    ]
    assert "ruff" in targets
    assert "ruff.lint" in targets
    assert len(targets) == len(set(targets))


def test_cargo_computed_workspace_glob_fails_closed():
    source = cargo_fixture().replace('"core"', '"crates/*"', 1)
    with pytest.raises(stage.PackageJsonError, match="dynamic_cargo_workspace_member"):
        extract_cargo(source)


def test_tox_environment_name_equal_to_prefix_fragment_has_exact_span():
    source = """[tox]
envlist = env, lint, docs, type

[testenv:env]
commands = pytest
[testenv:lint]
commands = ruff
[testenv:docs]
commands = sphinx
[testenv:type]
commands = mypy
[testenv:ci]
commands = tox -e env
"""
    encoded = source.encode("utf-8")
    row = extract_tox(source)[0]
    proof = row["source_provenance"]
    assert encoded[
        proof["definition_start_byte"]:proof["definition_end_byte"]
    ] == b"env"


def test_tox_case_equivalent_duplicate_options_fail_strictly():
    source = tox_fixture().replace(
        "commands = pytest",
        "commands = pytest\nCommands = other",
    )
    with pytest.raises(stage.PackageJsonError, match="invalid_or_duplicate_tox_ini"):
        extract_tox(source)


def test_pyproject_tool_name_equal_to_prefix_has_exact_span():
    source = pyproject_fixture("tool")
    encoded = source.encode("utf-8")
    row = next(
        row for row in extract_pyproject(source)
        if row["target"]["decoder_text"] == "tool"
    )
    proof = row["source_provenance"]
    assert encoded[
        proof["target_start_byte"]:proof["target_end_byte"]
    ] == b"tool"
    assert "[tool.<SCALAR>]" in row["input_text"]


def test_tox_colon_delimiter_matches_configparser_and_exact_spans():
    source = tox_fixture().replace(" = ", " : ")
    encoded = source.encode("utf-8")
    row = extract_tox(source)[0]
    proof = row["source_provenance"]
    assert encoded[
        proof["reference_target_start_byte"]:proof["reference_target_end_byte"]
    ] == b"py311"
    assert encoded[
        proof["definition_start_byte"]:proof["definition_end_byte"]
    ] == b"py311"


def test_tox_colon_forwarding_alias_is_excluded_without_emitting_a_row():
    source = tox_fixture().replace(
        "commands = tox -e py311",
        "commands: tox -e py311 -- --watch",
    )
    assert extract_tox(source) == []


@pytest.mark.parametrize("substitution", [
    "{env:HOME}",
    "{env:HOME:/tmp}",
    "{posargs}",
    "{toxworkdir}",
    "{toxinidir}",
    "{[base]commands}",
    "$HOME",
    "$(command)",
    "`command`",
])
def test_all_tox_substitution_forms_fail_before_row_extraction(substitution):
    source = tox_fixture().replace("commands = pytest", f"commands = {substitution}")
    with pytest.raises(stage.PackageJsonError, match="tox_interpolation_not_allowed"):
        extract_tox(source)


MAKE_BLOB = "3" * 40


def extract_make(source: str, **kwargs):
    return stage.extract_makefile_rows(
        source.encode("utf-8"),
        repository_key_sha256=REPO_KEY,
        revision=REVISION,
        source_blob_oid=MAKE_BLOB,
        **kwargs,
    )


def make_fixture(target: str = "test") -> str:
    return f"""# literal maintainer targets
build:
\techo build
lint:
\techo lint
test:
\techo test
docs:
\techo docs
ci:
\tmake {target}
"""


def test_make_exact_resolution_spans_hash_candidates_and_authority():
    import hashlib

    source = make_fixture()
    encoded = source.encode("utf-8")
    rows = extract_make(source)
    assert len(rows) == 1
    row = rows[0]
    assert row["ecosystem"] == "make"
    assert stage.MAKE_RECIPE_SCALAR_COMPLETION_SUPPORTED is False
    assert row["objective_family"] == "declarative_test_build_target_resolution"
    assert len(row["input_text"].split("candidates:\n", 1)[1].splitlines()) == 4
    assert all(value is False for value in row["authority"].values())
    proof = row["source_provenance"]
    assert encoded[
        proof["reference_target_start_byte"]:proof["reference_target_end_byte"]
    ] == b"test"
    assert encoded[
        proof["definition_start_byte"]:proof["definition_end_byte"]
    ] == b"test"
    assert proof["source_file_sha256"] == hashlib.sha256(encoded).hexdigest()


def test_make_real_target_mutation_preserves_input_and_changes_label():
    first = extract_make(make_fixture("test"))[0]
    second = extract_make(make_fixture("lint"))[0]
    assert first["input_text"] == second["input_text"]
    assert first["target"]["decoder_text"] != second["target"]["decoder_text"]
    assert first["row_id"] != second["row_id"]


def test_make_exactly_eight_candidates_must_emit_a_row():
    leaves = "".join(
        f"target{i}:\n\techo target{i}\n" for i in range(8)
    )
    rows = extract_make(leaves + "ci:\n\tmake target0\n")
    assert len(rows) == 1
    block = rows[0]["input_text"].split("candidates:\n", 1)[1]
    assert len(block.splitlines()) == 8


def test_make_suffix_compound_and_prefixed_aliases_are_not_candidates():
    source = """build:
\techo build
lint:
\techo lint
test:
\techo test
docs:
\techo docs
suffix:
\tmake test -- --watch
compound:
\tmake lint && echo done
prefixed:
\t@make docs
release:
\tmake build
"""
    rows = extract_make(source)
    assert len(rows) == 1
    block = rows[0]["input_text"].split("candidates:\n", 1)[1]
    assert '"suffix"' not in block
    assert "suffix:" not in block
    assert "compound:" not in block
    assert "prefixed:" not in block
    assert "release:" not in block
    assert len(block.splitlines()) == 4


@pytest.mark.parametrize("bad", [
    "a b:\n\techo ambiguous\n",
    "target::\n\techo double\n",
    "%.o:\n\techo pattern\n",
    "X = value\ntarget:\n\techo target\n",
    "include other.mk\ntarget:\n\techo target\n",
    "define RULE\ntarget:\n\techo target\nendef\n",
    "ifeq (a,b)\ntarget:\n\techo target\nendif\n",
    "target:\n\t$(MAKE) other\n",
    "target:\n\techo ${TARGET}\n",
    "target:\n\techo " + chr(96) + "command" + chr(96) + "\n",
    "target:\\\n\techo continued\n",
    ".PHONY: target\ntarget:\n\techo target\n",
    "target:\n\techo one\ntarget:\n\techo two\n",
    "\tmake target\n",
    "make target\n",
])
def test_make_dynamic_ambiguous_generated_and_orphan_forms_fail_closed(bad):
    with pytest.raises(stage.PackageJsonError):
        extract_make(bad)


def test_make_dependency_aggregators_are_not_real_candidates():
    source = make_fixture() + """aggregate: build lint
release:
\tmake build
"""
    row = next(
        row for row in extract_make(source)
        if "release:" in row["input_text"].split("invocation:", 1)[1]
    )
    block = row["input_text"].split("candidates:\n", 1)[1]
    assert "aggregate:" not in block


def test_make_multibyte_prefix_preserves_all_byte_spans():
    source = make_fixture().replace(
        "# literal maintainer targets",
        "# caf\u00e9 maintainer targets",
    ).replace("\techo build", "\techo caf\u00e9 build")
    encoded = source.encode("utf-8")
    row = extract_make(source)[0]
    proof = row["source_provenance"]
    assert encoded[
        proof["reference_target_start_byte"]:proof["reference_target_end_byte"]
    ] == b"test"
    assert encoded[
        proof["definition_start_byte"]:proof["definition_end_byte"]
    ] == b"test"


def test_make_identity_binds_repo_revision_blob_and_path():
    source = make_fixture().encode("utf-8")
    base = stage.extract_makefile_rows(
        source,
        repository_key_sha256=REPO_KEY,
        revision=REVISION,
        source_blob_oid=MAKE_BLOB,
    )[0]
    mutations = [
        stage.extract_makefile_rows(
            source,
            repository_key_sha256="d" * 64,
            revision=REVISION,
            source_blob_oid=MAKE_BLOB,
        )[0],
        stage.extract_makefile_rows(
            source,
            repository_key_sha256=REPO_KEY,
            revision="e" * 40,
            source_blob_oid=MAKE_BLOB,
        )[0],
        stage.extract_makefile_rows(
            source,
            repository_key_sha256=REPO_KEY,
            revision=REVISION,
            source_blob_oid="f" * 40,
        )[0],
        stage.extract_makefile_rows(
            source,
            repository_key_sha256=REPO_KEY,
            revision=REVISION,
            source_blob_oid=MAKE_BLOB,
            source_path="build/Makefile",
        )[0],
    ]
    assert len({base["row_id"], *(row["row_id"] for row in mutations)}) == 5


def test_make_never_emits_recipe_scalar_completion():
    rows = extract_make(make_fixture())
    assert rows
    assert stage.MAKE_RECIPE_SCALAR_COMPLETION_SUPPORTED is False
    assert all(
        row["objective_family"] != "declarative_test_build_scalar_completion"
        for row in rows
    )


def test_make_path_qualified_and_gmake_delegators_are_excluded():
    source = """build:
\techo build
lint:
\techo lint
test:
\techo test
docs:
\techo docs
path_alias:
\t/usr/bin/make test
gmake_alias:
\tgmake lint
release:
\tmake build
"""
    row = extract_make(source)[0]
    block = row["input_text"].split("candidates:\n", 1)[1]
    assert "path_alias:" not in block
    assert "gmake_alias:" not in block
    assert len(block.splitlines()) == 4


def test_make_crlf_offsets_reconstruct_exact_targets():
    source = make_fixture().replace("\n", "\r\n")
    encoded = source.encode("utf-8")
    row = extract_make(source)[0]
    proof = row["source_provenance"]
    assert encoded[
        proof["reference_target_start_byte"]:proof["reference_target_end_byte"]
    ] == b"test"
    assert encoded[
        proof["definition_start_byte"]:proof["definition_end_byte"]
    ] == b"test"


def test_make_safe_path_token_is_exactly_resolved():
    source = """pkg/test-v1:
\techo package
lint:
\techo lint
test:
\techo test
docs:
\techo docs
ci:
\tmake pkg/test-v1
"""
    encoded = source.encode("utf-8")
    row = extract_make(source)[0]
    proof = row["source_provenance"]
    assert encoded[
        proof["reference_target_start_byte"]:proof["reference_target_end_byte"]
    ] == b"pkg/test-v1"
    assert encoded[
        proof["definition_start_byte"]:proof["definition_end_byte"]
    ] == b"pkg/test-v1"


def _fake_release_scan():
    snapshots = []
    records = {}
    for index in range(10):
        component = f"component-{index}"
        repo = f"repo-{index}"
        snapshot = __import__("types").SimpleNamespace(
            repo_key=repo,
            component_key=component,
            revision=f"{index:x}".rjust(40, "0"),
            tree_oid=f"{index + 16:x}".rjust(40, "0"),
            component_objects=(("blob", f"{index + 32:x}".rjust(40, "0"), 100),),
        )
        row = {
            "row_id": f"stage12692_fake_{index}",
            "ecosystem": "npm",
            "objective_family": "declarative_test_build_target_resolution",
            "input_text": f"input-{index}",
            "target": {"decoder_text": f"candidate_{index % 4}"},
            "loss_mask": {"decoder_ce": True},
            "source_provenance": {
                "source_path": "package.json",
                "source_file_sha256": f"{index + 64:x}".rjust(64, "0"),
            },
            "authority": dict(stage.AUTHORITY),
        }
        proof = {
            "row_id": row["row_id"],
            "repository_key_sha256": repo,
            "content_component_sha256": component,
            "revision": snapshot.revision,
            "tree_oid": snapshot.tree_oid,
            "source_path": "package.json",
            "source_file_sha256": row["source_provenance"]["source_file_sha256"],
            "definition_evidence_sha256": f"{index + 96:x}".rjust(64, "0"),
            "candidate_evidence_sha256s": [f"{index + 128:x}".rjust(64, "0")],
            "model_input_sha256": f"{index + 160:x}".rjust(64, "0"),
            "semantic_example_sha256": f"{index + 192:x}".rjust(64, "0"),
            "objective_family": row["objective_family"],
        }
        snapshots.append(snapshot)
        records[component] = [(snapshot, row, proof)]
    scan = stage.SupplyScan(
        snapshots,
        records,
        __import__("collections").Counter(),
        {"whole_component_assignment": True},
    )
    return stage._bind_scan_commitment(
        scan,
        source_root_identity_sha256="f" * 64,
        max_repos=10,
        per_repo_cap=1,
    )


def test_supported_discovery_paths_exclude_yaml_and_unlisted_files(monkeypatch, tmp_path):
    tree_entries = (
        stage.stage12688.TreeEntry("100644", "blob", "1" * 40, 100, "package.json"),
        stage.stage12688.TreeEntry("100644", "blob", "2" * 40, 100, "nested/tox.ini"),
        stage.stage12688.TreeEntry("100644", "blob", "3" * 40, 100, "Cargo.toml"),
        stage.stage12688.TreeEntry("100644", "blob", "4" * 40, 100, "GNUmakefile"),
        stage.stage12688.TreeEntry("100644", "blob", "5" * 40, 100, "workflow.yaml"),
        stage.stage12688.TreeEntry("100644", "blob", "6" * 40, 100, "setup.cfg"),
    )
    snapshot = __import__("types").SimpleNamespace(
        tree_entries=tree_entries,
        blobs=[],
        estimated_row_capacity=0,
    )
    monkeypatch.setattr(
        stage.stage12688,
        "discover_repositories",
        lambda source_root, max_repos: ([snapshot], __import__("collections").Counter()),
    )
    snapshots, counters = stage.discover_pinned_snapshots(tmp_path, 1)
    assert snapshots == [snapshot]
    assert {blob.path for blob in snapshot.blobs} == {
        "package.json", "nested/tox.ini", "Cargo.toml", "GNUmakefile"
    }
    assert stage.YAML_SUPPORTED is False
    assert counters["stage12692_supported_blobs"] == 4


def test_real_git_head_discovery_and_no_publication_scan(tmp_path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "package.json").write_text(
        '{"scripts":{"build":"tsc","lint":"eslint .","test":"pytest",'
        '"docs":"sphinx","ci":"npm run test"}}\n',
        encoding="utf-8",
    )
    (repo / "workflow.yaml").write_text("jobs: {}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)

    scan = stage.scan_repository_supply(tmp_path, max_repos=1, per_repo_cap=20)
    assert scan.row_count == 1
    record = next(iter(scan.records_by_component.values()))[0]
    snapshot, row, proof = record
    assert row["ecosystem"] == "npm"
    assert row["source_provenance"]["revision"] == snapshot.revision
    assert proof["tree_oid"] == snapshot.tree_oid
    assert "workflow.yaml" not in {
        blob.path for blob in snapshot.blobs
    }


def test_cross_component_shared_source_definition_and_candidate_are_quarantined():
    scan = _fake_release_scan()
    first = scan.records_by_component["component-0"][0][2]
    second = scan.records_by_component["component-1"][0][2]
    second["source_file_sha256"] = first["source_file_sha256"]
    second["definition_evidence_sha256"] = first["definition_evidence_sha256"]
    second["candidate_evidence_sha256s"] = list(first["candidate_evidence_sha256s"])
    counters = __import__("collections").Counter()
    retained = stage._quarantine_and_deduplicate(scan.records_by_component, counters)
    assert "component-0" not in retained
    assert "component-1" not in retained
    assert counters["cross_component_evidence_rows_quarantined"] == 2


def test_component_split_is_exact_80_10_10_and_whole_component():
    scan = _fake_release_scan()
    rows, proofs, assignments = stage.materialize_split_rows(scan, 10)
    counts = __import__("collections").Counter(row["split"] for row in rows)
    assert counts == {"train": 8, "eval": 1, "strict_eval": 1}
    assert len(assignments) == 10
    owners = {}
    for proof in proofs:
        owners.setdefault(proof["content_component_sha256"], set()).add(proof["split"])
    assert all(len(splits) == 1 for splits in owners.values())


def test_release_strict_plaintext_is_absent_and_public_aggregates_are_train_eval_only():
    summary, payloads, rows, proofs = stage.prepare_release(_fake_release_scan(), 10)
    strict_ids = {
        row["row_id"] for row in rows if row["split"] == "strict_eval"
    }
    public_bytes = b"".join(payloads.values())
    assert strict_ids
    assert all(row_id.encode("ascii") not in public_bytes for row_id in strict_ids)
    assert summary["reserved_unmaterialized_strict_row_count"] == 1
    assert len(summary["strict_eval_commitment_sha256"]) == 64
    assert summary["materialized_train_eval_rows"] == 9
    assert sum(summary["objective_counts_train_eval_only"].values()) == 9
    assert "split_counts" not in summary
    assert summary["training_eligible_rows"] == 0
    assert all(value is False for value in summary["authority"].values())


def test_transactional_publication_modes_and_immutable_collision(tmp_path):
    output = tmp_path / "out"
    summary_path = tmp_path / "summary.json"
    summary = stage.publish_release(output, summary_path, _fake_release_scan(), 10)
    generation = output / "private" / summary["generation_id"]
    assert generation.is_dir()
    assert generation.stat().st_mode & 0o777 == 0o500
    for path in generation.iterdir():
        assert path.stat().st_mode & 0o777 == 0o400
    with pytest.raises(stage.Stage12692BuildError, match="immutable_publication_failed"):
        stage.publish_release(output, summary_path, _fake_release_scan(), 10)


def test_publication_race_failure_is_generic(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise stage.stage12688.Stage12688Error("attacker_controlled_detail")

    monkeypatch.setattr(stage.stage12687, "publish_generation", fail)
    with pytest.raises(stage.Stage12692BuildError) as caught:
        stage.publish_release(
            tmp_path / "out", tmp_path / "summary.json", _fake_release_scan(), 10
        )
    assert str(caught.value) == "immutable_publication_failed"
    assert "attacker" not in str(caught.value)


def test_capacity_scan_mode_has_no_default_and_no_publication(monkeypatch, capsys, tmp_path):
    scan = _fake_release_scan()
    monkeypatch.setattr(stage, "scan_repository_supply", lambda *args, **kwargs: scan)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--source-root", str(tmp_path),
            "--output-dir", str(tmp_path / "must-not-exist"),
            "--no-publication-capacity-scan",
        ],
    )
    assert stage.DEFAULT_MAX_ROWS == 1_880
    assert stage.main() == 0
    output = __import__("json").loads(capsys.readouterr().out)
    assert output["publication_performed"] is False
    assert output["post_filter_row_supply"] == 10
    assert not (tmp_path / "must-not-exist").exists()


def test_per_repository_cap_applies_after_accepted_parser_rows(monkeypatch):
    snapshot = __import__("types").SimpleNamespace(
        local_path=Path("/unused"),
        blobs=[stage.stage12688.Blob("a" * 40, 100, "package.json")],
        repo_key="b" * 64,
        revision="c" * 40,
        tree_oid="d" * 40,
        component_key="component",
    )
    source = (
        '{"scripts":{"a":"a","b":"b","c":"c","d":"d",'
        '"x":"npm run a","y":"npm run b","z":"npm run c"}}'
    ).encode("utf-8")
    monkeypatch.setattr(
        stage.stage12688, "cat_blobs", lambda repo, blobs: {"package.json": source}
    )
    counters = __import__("collections").Counter()
    records = stage._extract_snapshot_rows(snapshot, counters, 2)
    assert len(records) == 2
    assert counters["per_repository_cap_rows_skipped"] >= 1


def test_private_preopen_substitution_race_fails_inode_check(monkeypatch, tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    real_stat = stage.stage12687.os.stat
    raced = {"done": False}

    def racing_stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if (
            path == "private"
            and kwargs.get("dir_fd") is not None
            and kwargs.get("follow_symlinks") is False
            and not raced["done"]
        ):
            parent_fd = kwargs["dir_fd"]
            stage.stage12687.os.rename(
                "private",
                "private-before-substitution",
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            stage.stage12687.os.mkdir("private", 0o700, dir_fd=parent_fd)
            raced["done"] = True
        return result

    monkeypatch.setattr(stage.stage12687.os, "stat", racing_stat)
    with pytest.raises(
        stage.Stage12692BuildError, match="immutable_publication_failed"
    ):
        stage.publish_release(
            output, tmp_path / "summary.json", _fake_release_scan(), 10
        )
    assert raced["done"] is True
    assert list((output / "private").iterdir()) == []


def test_private_creation_fsyncs_pinned_output_parent(monkeypatch, tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    output_stat = output.stat()
    output_identity = (output_stat.st_dev, output_stat.st_ino)
    real_fsync = stage.stage12687.os.fsync
    fsynced_identities = []

    def tracking_fsync(fd):
        opened = stage.stage12687.os.fstat(fd)
        fsynced_identities.append((opened.st_dev, opened.st_ino))
        return real_fsync(fd)

    monkeypatch.setattr(stage.stage12687.os, "fsync", tracking_fsync)
    summary = stage.publish_release(
        output, tmp_path / "summary.json", _fake_release_scan(), 10
    )
    assert output_identity in fsynced_identities
    generation = output / "private" / summary["generation_id"]
    assert generation.is_dir()


def test_stale_10_row_scan_commitment_rejects_injected_1882_supply():
    scan = _fake_release_scan()
    original = scan.records_by_component["component-0"][0]
    scan.records_by_component["component-0"] = [original] * 1_873
    assert scan.row_count == 1_882
    with pytest.raises(
        stage.Stage12692BuildError, match="capacity_scan_commitment_mismatch"
    ):
        stage.materialize_split_rows(scan, 10)


def test_candidate_position_permutation_has_same_exact_evidence_and_quarantines():
    source = b'alpha:\n\techo alpha\nbeta:\n\techo beta\n'
    alpha_start = source.index(b"alpha:")
    beta_start = source.index(b"beta:")
    common = {
        "source_path": "Makefile",
        "source_git_blob_oid": "a" * 40,
        "source_file_sha256": __import__("hashlib").sha256(source).hexdigest(),
    }
    first_provenance = {
        **common,
        "candidate_definition_spans": [
            {"start_byte": alpha_start, "end_byte": alpha_start + len(b"alpha:")},
            {"start_byte": beta_start, "end_byte": beta_start + len(b"beta:")},
        ],
    }
    second_provenance = {
        **common,
        "candidate_definition_spans": list(
            reversed(first_provenance["candidate_definition_spans"])
        ),
    }
    first_evidence = stage._candidate_evidence(source, first_provenance)
    second_evidence = stage._candidate_evidence(source, second_provenance)
    assert first_evidence == second_evidence
    assert all("candidate_" not in value for value in first_evidence)

    scan = _fake_release_scan()
    first = scan.records_by_component["component-0"][0]
    second = scan.records_by_component["component-1"][0]
    first[1]["input_text"] = "candidate_0: alpha\ncandidate_1: beta"
    second[1]["input_text"] = "candidate_0: beta\ncandidate_1: alpha"
    first[2]["candidate_evidence_sha256s"] = first_evidence
    second[2]["candidate_evidence_sha256s"] = list(reversed(second_evidence))
    counters = __import__("collections").Counter()
    retained = stage._quarantine_and_deduplicate(scan.records_by_component, counters)
    assert "component-0" not in retained
    assert "component-1" not in retained
    assert counters["cross_component_evidence_rows_quarantined"] == 2


def test_public_release_exposes_scan_commitment_not_private_capacities():
    summary, _, _, _ = stage.prepare_release(_fake_release_scan(), 10)
    assert summary["capacity_scan_commitment_sha256"]
    assert "capacity_scan_evidence" not in summary
    assert "component_capacities" not in summary
    assert "post_filter_row_supply" not in summary
    assert "component_count" not in summary

def test_full_preparation_preserves_splits_commitment_and_legacy_public_bytes():
    scan = _fake_release_scan()
    expected_rows, expected_proofs, _ = stage.materialize_split_rows(scan, 10)
    prepared = stage.prepare_full_release(scan, 10)
    summary, payloads, rows, proofs = stage.prepare_release(scan, 10)

    assert rows == prepared.rows == expected_rows
    assert proofs == prepared.proofs == expected_proofs
    assert __import__("collections").Counter(
        row["split"] for row in prepared.rows
    ) == {"train": 8, "eval": 1, "strict_eval": 1}
    assert summary == prepared.summary
    assert payloads == prepared.public_payloads
    assert summary["reserved_unmaterialized_strict_row_count"] == 1
    assert summary["strict_eval_commitment_sha256"] == stage.stage12688.stable(
        sorted(
            proof["row_sha256"]
            for proof in prepared.proofs
            if proof["split"] == "strict_eval"
        )
    )
    assert len([
        entry for entry in prepared.catalog
        if entry["split"] == "strict_eval"
    ]) == 1
    assert stage._jsonl([
        entry for entry in prepared.catalog
        if entry["split"] != "strict_eval"
    ]) == payloads["train_eval_source_catalog.jsonl"]
