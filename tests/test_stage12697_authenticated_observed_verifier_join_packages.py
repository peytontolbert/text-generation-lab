from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12697_authenticated_observed_verifier_join_packages.py"
CONFIG = ROOT / "configs/software_maintainer/stage12697_pinned_observation_sources_v1.json"
SPEC = importlib.util.spec_from_file_location("stage12697_tested", SCRIPT)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = S
SPEC.loader.exec_module(S)


@pytest.fixture(scope="module")
def production():
    return S.build_packages()


def test_exhaustive_honest_production_count_and_reasons(production):
    assert production["stage12537_members_examined"] == 13
    assert production["stage12125_members_examined"] == 3
    assert production["stage12123_members_examined"] == 12
    assert len(production["discovery_audit"]) == 13
    assert len({row["stage12537_member_sha256"] for row in production["discovery_audit"]}) == 13
    assert production["discovered_join_package_count"] == 3
    assert production["rejected_stage12537_candidate_count"] == 10
    assert production["rejection_reason_counts"] == {
        "no_pinned_stage12125_report_stream_match": 10,
        "source_stage_not_stage12125": 10,
    }



def test_private_materialization_inputs_are_exact_and_committed(production):
    assert len(production["materialization_inputs"]) == 3
    packages = {row["package_sha256"]: row for row in production["packages"]}
    roles = {"stage12537", "result", "report", "commit", "smoke", "join"}
    for bundle in production["materialization_inputs"]:
        package = packages[bundle["package_sha256"]]
        assert set(bundle["records"]) == roles
        assert set(bundle["raw_records"]) == roles
        assert set(bundle["raw_record_sha256s"]) == roles
        for role in roles:
            raw = bundle["raw_records"][role]
            assert json.loads(raw) == bundle["records"][role]
            assert hashlib.sha256(raw).hexdigest() == (
                bundle["raw_record_sha256s"][role]
            )
        assert not any(bundle["authority"].values())
        assert "placeholder" not in repr(bundle["records"]).lower()
        S.validate_materialization_input(bundle, package)


def test_private_materialization_input_tampering_rejected(production):
    package = production["packages"][0]
    bundle = next(
        row for row in production["materialization_inputs"]
        if row["package_sha256"] == package["package_sha256"]
    )
    tampered_raw = copy.deepcopy(bundle)
    tampered_raw["raw_records"]["join"] = b"{}"
    with pytest.raises(S.Stage12697Error, match="raw_binding"):
        S.validate_materialization_input(tampered_raw, package)

    tampered_commitment = copy.deepcopy(bundle)
    tampered_commitment["materialization_input_commitment_sha256"] = "f" * 64
    with pytest.raises(S.Stage12697Error, match="commitment_invalid"):
        S.validate_materialization_input(tampered_commitment, package)


def test_main_never_emits_private_materialization_inputs(capsys):
    assert S.main() == 0
    public = json.loads(capsys.readouterr().out)
    assert "packages" not in public
    assert "discovery_audit" not in public
    assert "materialization_inputs" not in public


def test_head_only_snapshot_packages_are_committed_without_parent_traversal(production):
    assert sorted(package["target"]["counts"]["passed"] for package in production["packages"]) == [1, 1, 10]
    for package in production["packages"]:
        snapshot = package["snapshot"]
        assert snapshot["snapshot_contract"] == "descriptor_pinned_exact_shallow_head_only_v1"
        assert snapshot["parents_traversed"] is False
        assert snapshot["revision"]
        assert snapshot["root_tree_oid"]
        assert snapshot["tree_placements"] > 0
        assert snapshot["blob_count"] > 0
        commitment = snapshot["snapshot_commitment_sha256"]
        unsigned = dict(snapshot)
        unsigned.pop("snapshot_commitment_sha256")
        assert commitment == S._stable([
            "stage12697_descriptor_pinned_shallow_head_snapshot_v1", unsigned,
        ])
        assert set(item[2] for item in snapshot["blob_inventory"]) <= {
            "100644", "100755", "120000",
        }
        assert all(item[2] == "160000" for item in snapshot["gitlink_inventory"])


def test_no_seeded_join_specs_or_fixed_capacity():
    text = SCRIPT.read_text()
    assert "JOIN_SPECS" not in text
    assert "capacity_not_exactly_three" not in text
    assert '"discovered_join_package_count": 3' not in text


def test_authority_claims_and_side_effects_remain_closed(production):
    assert production["external_cryptographic_authentication"] is False
    assert production["publication_performed"] is False
    assert production["verifier_execution_performed"] is False
    assert production["read_only_git_inspection_performed"] is True
    assert "execution_performed" not in production
    assert '"execution_performed"' not in SCRIPT.read_text()
    assert production["training_eligible_rows"] == 0
    assert all(value is False for value in production["authority"].values())
    text = SCRIPT.read_text()
    assert "subprocess" not in text
    assert "write_text" not in text and "write_bytes" not in text


def test_stage12696_loader_executes_reviewed_bytes_not_reopened_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "dependency.py"
    path.write_text("VALUE = \"replaced\"\n", encoding="utf-8")
    trusted = b"VALUE = \"trusted\"\n"
    monkeypatch.setattr(S, "_read_pinned", lambda *_args, **_kwargs: trusted)
    module = S._load_stage12696(tmp_path, {
        "stage12696_interface": {
            "path": "dependency.py",
            "sha256": hashlib.sha256(trusted).hexdigest(),
        },
    })
    assert module.VALUE == "trusted"


def test_separate_manifest_digest_and_residual_trust_contract(production):
    raw = CONFIG.read_bytes()
    manifest = json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == S.REVIEWED_CONFIG_SHA256
    assert production["reviewed_config_sha256"] == S.REVIEWED_CONFIG_SHA256
    assert manifest["claim_boundary"]["external_cryptographic_authentication"] is False
    assert manifest["claim_boundary"]["residual_trust"] == production["residual_trust"]
    assert production["stage12696_interface_sha256"] == manifest["stage12696_interface"]["sha256"]
    assert set(manifest["implementation_dependencies"]) == {
        "stage12687", "stage12688", "stage12690", "stage12692", "stage12693",
    }
    for name, dependency in manifest["implementation_dependencies"].items():
        key = f"{name}_implementation_sha256"
        assert production[key] == dependency["sha256"]
        assert hashlib.sha256((ROOT / dependency["path"]).read_bytes()).hexdigest() == dependency["sha256"]
    for package in production["packages"]:
        for name in manifest["implementation_dependencies"]:
            key = f"{name}_implementation_sha256"
            assert package[key] == production[key]
    builder = SCRIPT.read_text()
    for source in manifest["sources"].values():
        assert source["sha256"] not in builder


def test_local_import_closure_is_exactly_manifest_pinned():
    manifest = json.loads(CONFIG.read_text())
    dependencies = manifest["implementation_dependencies"]
    expected = {Path(entry["path"]).name for entry in dependencies.values()}
    inspected = [manifest["stage12696_interface"]["path"]]
    inspected.extend(entry["path"] for entry in dependencies.values())
    discovered = set()
    for relative in inspected:
        tree = ast.parse((ROOT / relative).read_text(), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("build_stage"):
                        discovered.add(alias.name.rpartition(".")[2] + ".py")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("build_stage"):
                    discovered.add(node.module.rpartition(".")[2] + ".py")
            elif isinstance(node, ast.Call):
                for argument in (*node.args, *node.keywords):
                    value = argument.value if isinstance(argument, ast.keyword) else argument
                    if (
                        isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                        and Path(value.value).name.startswith("build_stage")
                        and Path(value.value).suffix == ".py"
                    ):
                        discovered.add(Path(value.value).name)
    assert discovered == expected


def _copy_manifest_inputs(destination: Path):
    manifest = json.loads(CONFIG.read_text())
    paths = [S.CONFIG_PATH, manifest["stage12696_interface"]["path"]]
    paths.extend(entry["path"] for entry in manifest["implementation_dependencies"].values())
    paths.extend(entry["path"] for entry in manifest["sources"].values())
    for relative in paths:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return manifest


def test_manifest_mutation_rejected_before_source_use(tmp_path):
    _copy_manifest_inputs(tmp_path)
    path = tmp_path / S.CONFIG_PATH
    value = json.loads(path.read_text())
    value["claim_boundary"]["external_cryptographic_authentication"] = True
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    with pytest.raises(S.Stage12697Error, match="source_digest_mismatch"):
        S.build_packages(tmp_path)


def test_coordinated_source_reseal_rejected_by_manifest_pin(tmp_path):
    manifest = _copy_manifest_inputs(tmp_path)
    relative = manifest["sources"]["stage12125_results"]["path"]
    path = tmp_path / relative
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["repo_family"] = "forged/resealed"
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    with pytest.raises(S.Stage12697Error, match="source_digest_mismatch"):
        S.build_packages(tmp_path)


@pytest.mark.parametrize("dependency", [
    "stage12687",
    "stage12688",
    "stage12690",
    "stage12692",
    "stage12693",
])
def test_implementation_dependency_digest_mismatch_rejected(tmp_path, dependency):
    manifest = _copy_manifest_inputs(tmp_path)
    path = tmp_path / manifest["implementation_dependencies"][dependency]["path"]
    path.write_bytes(path.read_bytes() + b"\n# forged\n")
    with pytest.raises(S.Stage12697Error, match="source_digest_mismatch"):
        S.build_packages(tmp_path)


@pytest.mark.parametrize("selector", [
    "", "/absolute", "../up", "a/../b", "a\\b", "a//b", "a/", ".", "a\x00b",
])
def test_all_forbidden_path_selectors_rejected(selector):
    with pytest.raises(S.Stage12697Error, match="path_selector"):
        S._parts(selector)


def test_descriptor_relative_file_and_directory_resolution(tmp_path):
    (tmp_path / "testing").mkdir()
    (tmp_path / "testing" / "test_one.py").write_text("def test_one(): pass\n")
    (tmp_path / "build").mkdir()
    S._resolve_selector(str(tmp_path), "testing/test_one.py", directory=False)
    S._resolve_selector(str(tmp_path), "build", directory=True)


def test_descriptor_relative_resolution_rejects_symlink_parent_and_leaf(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "test.py").write_text("pass\n")
    (tmp_path / "parent").symlink_to("real", target_is_directory=True)
    (tmp_path / "leaf.py").symlink_to("real/test.py")
    with pytest.raises(S.Stage12697Error, match="resolution_failed"):
        S._resolve_selector(str(tmp_path), "parent/test.py", directory=False)
    with pytest.raises(S.Stage12697Error, match="resolution_failed"):
        S._resolve_selector(str(tmp_path), "leaf.py", directory=False)


def test_checkout_root_rejects_symlinked_absolute_component(tmp_path):
    real = tmp_path / "real"
    (real / "checkout").mkdir(parents=True)
    (real / "checkout" / "test.py").write_text("pass\n")
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(S.Stage12697Error, match="checkout_root_descriptor"):
        S._resolve_selector(str(alias / "checkout"), "test.py", directory=False)


def test_exact_shallow_boundary_is_required(tmp_path):
    git_dir = tmp_path / "git"
    git_dir.mkdir()
    head = "a" * 40
    shallow = git_dir / "shallow"
    shallow.write_text(head + "\n")
    repo = type("Repo", (), {})()
    repo.git_fd = __import__("os").open(git_dir, __import__("os").O_RDONLY | __import__("os").O_DIRECTORY)
    try:
        assert S._read_shallow_boundary(repo, head) == hashlib.sha256((head + "\n").encode()).hexdigest()
        shallow.write_text(head + "\n" + "b" * 40 + "\n")
        with pytest.raises(S.Stage12697Error, match="not_exact_expected_head"):
            S._read_shallow_boundary(repo, head)
        shallow.write_text("b" * 40 + "\n")
        with pytest.raises(S.Stage12697Error, match="not_exact_expected_head"):
            S._read_shallow_boundary(repo, head)
    finally:
        __import__("os").close(repo.git_fd)


def test_shallow_boundary_symlink_rejected(tmp_path):
    git_dir = tmp_path / "git"
    git_dir.mkdir()
    (git_dir / "real").write_text("a" * 40 + "\n")
    (git_dir / "shallow").symlink_to("real")
    repo = type("Repo", (), {})()
    repo.git_fd = __import__("os").open(git_dir, __import__("os").O_RDONLY | __import__("os").O_DIRECTORY)
    try:
        with pytest.raises(S.Stage12697Error, match="descriptor_open"):
            S._read_shallow_boundary(repo, "a" * 40)
    finally:
        __import__("os").close(repo.git_fd)


def test_snapshot_object_resource_bound_quarantines_plausible_joins(monkeypatch):
    monkeypatch.setattr(S, "MAX_SNAPSHOT_BLOBS", 1)
    result = S.build_packages()
    assert result["discovered_join_package_count"] == 0
    assert result["rejected_stage12537_candidate_count"] == 13
    assert result["rejection_reason_counts"]["snapshot_blob_count_limit_exceeded"] == 3


@pytest.mark.parametrize("argv", [
    ["python", "-m", "pytest", "-q", "test.py", "-k", "one"],
    ["python", "-m", "pytest", "-q", "/tmp/test.py"],
    ["python", "-m", "pytest", "-q", "../test.py"],
    ["python", "-m", "pytest", "--disable-warnings", "-q", "test.py"],
    ["ctest", "--test-dir", "/tmp/build", "--output-on-failure", "-R", "^one$"],
    ["ctest", "--test-dir", "../build", "--output-on-failure", "-R", "^one$"],
    ["ctest", "--test-dir", "build", "--output-on-failure", "-R", "one"],
    ["ctest", "--test-dir", "build", "--output-on-failure", "-R", "^one$", "-V"],
])
def test_run_argv_unknown_options_and_escaping_paths_rejected(argv):
    with pytest.raises(S.Stage12697Error):
        S._allowlist_run_argv(argv)


def test_actual_run_argv_forms_are_allowlisted():
    assert S._allowlist_run_argv(
        ["python", "-m", "pytest", "-q", "testing/test_details.py"]
    ) == ("pytest", "testing/test_details.py", None)
    assert S._allowlist_run_argv(
        ["ctest", "--test-dir", "build", "--output-on-failure", "-R", "^one$"]
    ) == ("ctest", "build", "^one$")


def pytest_run(summary: str = "2 passed in 0.01s", prefix: str = "") -> str:
    return prefix + ".. [100%]\n" + summary + "\n"


def test_pytest_strict_pass_accepts_only_passes():
    parsed = S.parse_strict_run(
        ["python", "-m", "pytest", "-q", "testing/test_one.py"],
        pytest_run(), "",
    )
    assert parsed["counts"] == {
        "passed": 2, "failed": 0, "errors": 0,
        "skipped": 0, "xfailed": 0, "xpassed": 0,
    }


@pytest.mark.parametrize("summary", [
    "1 passed, 1 skipped in 0.01s",
    "1 passed, 1 xfailed in 0.01s",
    "1 passed, 1 xpassed in 0.01s",
    "1 passed, 1 failed in 0.01s",
    "1 passed, 1 error in 0.01s",
])
def test_pytest_non_strict_outcomes_rejected(summary):
    with pytest.raises(S.Stage12697Error, match="not_strict_pass"):
        S.parse_strict_run(["python", "-m", "pytest", "-q", "x.py"], pytest_run(summary), "")


def test_pytest_conflicting_earlier_terminal_summary_rejected():
    stdout = "1 failed in 0.01s\n. [100%]\n1 passed in 0.01s\n"
    with pytest.raises(S.Stage12697Error, match="output_grammar"):
        S.parse_strict_run(["python", "-m", "pytest", "-q", "x.py"], stdout, "")


@pytest.mark.parametrize("stdout,stderr,reason", [
    (pytest_run(prefix="ERROR collecting testing/test_one.py\n"), "", "environment_setup"),
    (pytest_run(), "warning: not reviewed benign\n", "stderr_not_explicitly_benign"),
    ("1 test collected in 0.01s\n", "", "output_grammar"),
    (pytest_run(prefix="RuntimeError: fatal exception\n"), "", "environment_setup"),
    (pytest_run(prefix="an unmatched benign line\n"), "", "output_grammar"),
])
def test_pytest_environment_stderr_and_collection_only_rejected(stdout, stderr, reason):
    with pytest.raises(S.Stage12697Error, match=reason):
        S.parse_strict_run(["python", "-m", "pytest", "-q", "x.py"], stdout, stderr)


def ctest_stdout(
    result: str = "1/1 Test #1: one ........ Passed 0.01 sec",
    summary: str = "100% tests passed, 0 tests failed out of 1",
    prefix: str = "",
    total: str = "Total Test time (real) = 0.01 sec",
) -> str:
    return (
        prefix
        + "Internal ctest changing into directory: /tmp/checkout/build\n"
        + "Test project /tmp/checkout/build\n"
        + "Start 1: one\n"
        + result + "\n" + summary + "\n" + total + "\n"
    )


def test_ctest_strict_pass():
    parsed = S.parse_strict_run(["ctest", "--test-dir", "build"], ctest_stdout(), "")
    assert parsed["test_names"] == ["one"]


@pytest.mark.parametrize("stdout,reason", [
    (ctest_stdout(prefix="Errors while running CTest\n"), "output_grammar"),
    (ctest_stdout(prefix="Failure details were emitted\n"), "output_grammar"),
    (ctest_stdout(result="1/1 Test #1: one ***Failed 0.01 sec",
                  summary="0% tests passed, 1 tests failed out of 1"), "not_strict_pass"),
    (ctest_stdout(total="Total Test time (real) = forged"), "output_grammar"),
    (ctest_stdout(prefix="100% tests passed, 0 tests failed out of 1\n"), "output_grammar"),
    (ctest_stdout(prefix="fatal exception\n"), "output_grammar"),
])
def test_ctest_failure_environment_and_conflicting_summaries_rejected(stdout, reason):
    with pytest.raises(S.Stage12697Error, match=reason):
        S.parse_strict_run(["ctest", "--test-dir", "build"], stdout, "")


def test_ctest_duplicate_ids_and_ordinals_rejected():
    stdout = (
        "1/2 Test #1: one Passed 0.01 sec\n"
        "2/2 Test #1: two Passed 0.01 sec\n"
        "100% tests passed, 0 tests failed out of 2\n"
        "Total Test time (real) = 0.02 sec\n"
    )
    with pytest.raises(S.Stage12697Error, match="output_grammar"):
        S.parse_strict_run(["ctest"], stdout, "")


def test_every_present_exit_and_timeout_field_must_agree():
    S._field_agreement([
        {"exit_code": 0, "timeout": False},
        {"process_exit_code": 0, "session_exit_code": 0, "timeout": False},
    ])
    with pytest.raises(S.Stage12697Error, match="exit_fields"):
        S._field_agreement([{"exit_code": 0}, {"session_exit_code": 1}])
    with pytest.raises(S.Stage12697Error, match="timeout_fields"):
        S._field_agreement([{"exit_code": 0, "timeout": False},
                            {"process_exit_code": 0, "timeout": True}])
    with pytest.raises(S.Stage12697Error, match="exit_field_invalid"):
        S._field_agreement([{"exit_code": False}])


def valid_collection():
    argv = ["python", "-m", "pytest", "--collect-only", "-q", "testing/test_one.py"]
    stdout = (
        "testing/test_one.py::test_a\n"
        "testing/test_one.py::test_b\n\n"
        "2 tests collected in 0.01s\n"
    )
    return argv, stdout


def test_pytest_collection_report_parses_exact_nodes():
    argv, stdout = valid_collection()
    assert S.parse_pytest_collection(argv, stdout, "") == [
        "testing/test_one.py::test_a", "testing/test_one.py::test_b",
    ]


@pytest.mark.parametrize("mutator,reason", [
    (lambda argv, out: (["python", "-m", "pytest", "-q", "testing/test_one.py"], out),
     "argv_not_allowlisted"),
    (lambda argv, out: (argv, out.replace("2 tests collected", "3 tests collected")),
     "count_or_identity"),
    (lambda argv, out: (argv, out.replace("testing/test_one.py::test_b",
                                         "testing/test_one.py::test_a")),
     "count_or_identity"),
    (lambda argv, out: (argv, out.replace("testing/test_one.py::test_b", "../test.py::test_b")),
     "path_selector"),
])
def test_pytest_collection_critic_mutations_rejected(mutator, reason):
    argv, stdout = valid_collection()
    argv, stdout = mutator(argv, stdout)
    with pytest.raises(S.Stage12697Error, match=reason):
        S.parse_pytest_collection(argv, stdout, "")


def test_capture_bound_rejects_possible_truncation():
    stdout = "x" * S.SOURCE_STREAM_CAPTURE_LIMIT + "\n1 passed in 0.01s\n"
    with pytest.raises(S.Stage12697Error, match="may_be_truncated"):
        S.parse_strict_run(["python", "-m", "pytest", "-q", "x.py"], stdout, "")
