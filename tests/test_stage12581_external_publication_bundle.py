from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12581_external_publication_bundle.py"
SPEC = importlib.util.spec_from_file_location("stage12581", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def _copy_inputs(tmp_path: Path) -> Path:
    for spec in M.FILE_SPECS:
        source = ROOT / spec.path
        destination = tmp_path / spec.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return tmp_path


def _reason_present(result, suffix: str) -> bool:
    return any(reason == suffix or reason.endswith(f":{suffix}") for reason in result["blocking_reasons"])


def _write_canonical(path: Path, value) -> None:
    path.write_bytes(M.canonical_json_bytes(value))


def test_production_bundle_is_exact_minimal_fixed_order_and_deterministic():
    first = M.build_stage()
    second = M.build_stage()
    assert first == second
    assert first["local_bundle_valid"] is True
    assert first["decision"] == "content_only_publication_bundle_constructed_unpublished_zero_credit"
    assert first["file_count"] == 3
    assert first["total_size_bytes"] == sum(spec.size_bytes for spec in M.FILE_SPECS)
    assert [entry["ordinal"] for entry in first["ordered_files"]] == [0, 1, 2]
    assert [entry["path"] for entry in first["ordered_files"]] == list(M.EXPECTED_PATHS)
    assert [entry["sha256"] for entry in first["ordered_files"]] == [spec.sha256 for spec in M.FILE_SPECS]
    assert [entry["size_bytes"] for entry in first["ordered_files"]] == [spec.size_bytes for spec in M.FILE_SPECS]
    assert first["ordered_files"][1]["role"] == "stage12580_unpublished_local_identity_preimage_zero_credit"
    assert first["content_only_publication_bundle"] is True
    assert first["clean_clone_reproducible"] is False
    assert first["implementation_and_tests_included"] is False
    assert first["local_bundle_valid_scope"] == "byte_integrity_and_cross_file_linkage_only"


def test_bundle_and_root_hashes_are_domain_separated_and_recomputable():
    result = M.build_stage()
    entries = result["ordered_files"]
    leaves = [
        M.stable_hash({"domain": M.LEAF_DOMAIN, "version": M.VERSION, **entry})
        for entry in entries
    ]
    assert result["ordered_leaf_sha256"] == leaves
    assert result["ordered_bundle_sha256"] == M.stable_hash({
        "domain": M.BUNDLE_DOMAIN,
        "version": M.VERSION,
        "files": entries,
    })
    assert result["bundle_root_sha256"] == M.stable_hash({
        "domain": M.ROOT_DOMAIN,
        "version": M.VERSION,
        "ordered_leaf_sha256": leaves,
    })
    assert result["ordered_bundle_sha256"] != result["bundle_root_sha256"]


def test_unpublished_timestamp_absent_and_all_authority_or_use_gates_are_false():
    result = M.build_stage()
    assert result["publication_not_yet_performed"] is True
    assert result["external_timestamp_absent"] is True
    assert result["acquisition_blocked"] is True
    assert set(M.STATUS_BLOCKERS) <= set(result["blocking_reasons"])
    assert all(result[key] is False for key in M.FALSE_GATES)
    assert not any(key in result for key in ("commands", "shell", "suggested_git_plan"))


def test_git_validation_uses_only_fixed_read_only_argv_without_shell_or_globs(monkeypatch):
    calls = []

    class Completed:
        returncode = 1

    def capture(argv, **kwargs):
        calls.append((argv, kwargs))
        return Completed()

    monkeypatch.setattr(M.subprocess, "run", capture)
    result = M.build_stage()
    expected = [M._git_check_ignore_argv(path) for path in M.EXPECTED_PATHS]
    assert [argv for argv, _kwargs in calls] == expected
    assert result["read_only_git_validation_performed"] is True
    assert result["read_only_git_validation_argv"] == expected
    assert result["write_capable_git_execution_performed"] is False
    assert result["publication_git_argv_emitted"] is False
    assert result["publication_git_execution_performed"] is False
    assert result["embedded_unexecuted_acquisition_argv_present"] is True
    assert result["embedded_acquisition_argv_executed"] is False
    write_capable = {
        "add", "am", "apply", "branch", "checkout", "cherry-pick", "clean", "commit",
        "merge", "mv", "push", "rebase", "reset", "revert", "rm", "stash", "switch", "tag",
    }
    assert all(argv[0:2] == ["git", "check-ignore"] for argv, _kwargs in calls)
    assert all(argv[1] not in write_capable for argv, _kwargs in calls)
    assert all(kwargs.get("shell", False) is False for _argv, kwargs in calls)
    assert all(
        not any(character in argument for character in "*?[")
        for argv, _kwargs in calls
        for argument in argv
    )
    assert all(argv[-1] in M.EXPECTED_PATHS and argv[-2] == "--" for argv, _kwargs in calls)


def test_caller_file_lists_are_rejected_even_when_exact():
    result = M.build_stage(file_paths=M.EXPECTED_PATHS)
    assert result["local_bundle_valid"] is False
    assert result["ordered_files"] == []
    assert result["ordered_bundle_sha256"] is None
    assert result["bundle_root_sha256"] is None
    assert "caller_file_list_rejected" in result["blocking_reasons"]


def test_unrelated_private_raw_and_runtime_weight_paths_are_rejected():
    paths = [
        *M.EXPECTED_PATHS,
        "runs/local/private/raw_data/model.safetensors",
        "README.md",
    ]
    result = M.build_stage(file_paths=paths)
    assert result["local_bundle_valid"] is False
    assert "caller_file_list_mismatch" in result["blocking_reasons"]
    assert "unrelated_path_rejected" in result["blocking_reasons"]
    assert "private_or_raw_path_rejected" in result["blocking_reasons"]
    assert "runtime_weight_type_rejected" in result["blocking_reasons"]
    assert "file_type_not_allowlisted" in result["blocking_reasons"]


def test_changed_canonical_bytes_fail_closed_on_hash_and_size(tmp_path):
    root = _copy_inputs(tmp_path)
    path = root / M.FILE_SPECS[1].path
    value = json.loads(path.read_bytes())
    value["decision"] = "tampered"
    _write_canonical(path, value)
    result = M._build_fixed(root, ignore_check=lambda _root, _path: False)
    assert result["local_bundle_valid"] is False
    assert _reason_present(result, "selected_file_sha256_mismatch")
    assert _reason_present(result, "selected_file_size_mismatch")
    assert result["ordered_files"] == []
    assert result["ordered_bundle_sha256"] is None


def test_missing_dependency_fails_closed(tmp_path):
    root = _copy_inputs(tmp_path)
    (root / M.FILE_SPECS[0].path).unlink()
    result = M._build_fixed(root, ignore_check=lambda _root, _path: False)
    assert result["local_bundle_valid"] is False
    assert _reason_present(result, "required_file_missing")
    assert "required_dependency_set_unavailable" in result["blocking_reasons"]


def test_symlink_selected_file_is_rejected_without_following_it(tmp_path):
    root = _copy_inputs(tmp_path)
    path = root / M.FILE_SPECS[2].path
    target = root / "target.json"
    target.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(target)
    result = M._build_fixed(root, ignore_check=lambda _root, _path: False)
    assert result["local_bundle_valid"] is False
    assert _reason_present(result, "symlink_rejected")
    assert result["bundle_root_sha256"] is None


def test_large_selected_file_is_rejected_before_json_use(tmp_path):
    root = _copy_inputs(tmp_path)
    path = root / M.FILE_SPECS[0].path
    path.write_bytes(b" " * (M.MAX_FILE_BYTES + 1))
    result = M._build_fixed(root, ignore_check=lambda _root, _path: False)
    assert result["local_bundle_valid"] is False
    assert _reason_present(result, "file_too_large")
    assert result["ordered_files"] == []


def test_outcome_and_raw_fields_are_rejected_recursively(tmp_path):
    root = _copy_inputs(tmp_path)
    path = root / M.FILE_SPECS[1].path
    value = json.loads(path.read_bytes())
    value["nested"] = {"outcome": "pass", "raw_data": [1, 2, 3]}
    _write_canonical(path, value)
    result = M._build_fixed(root, ignore_check=lambda _root, _path: False)
    assert result["local_bundle_valid"] is False
    assert _reason_present(result, "forbidden_outcome_private_or_raw_field")
    assert result["bundle_root_sha256"] is None


def test_git_ignored_selected_file_fails_closed(tmp_path):
    root = _copy_inputs(tmp_path)
    ignored = M.FILE_SPECS[0].path
    result = M._build_fixed(root, ignore_check=lambda _root, path: path == ignored)
    assert result["local_bundle_valid"] is False
    assert _reason_present(result, "git_ignored_file_rejected")
    assert result["ordered_files"] == []


def test_prior_stage_links_and_exact_bytes_are_validated():
    documents = [json.loads((ROOT / spec.path).read_bytes()) for spec in M.FILE_SPECS]
    assert M._cross_file_reasons(documents) == []
    for spec, document in zip(M.FILE_SPECS, documents):
        raw = (ROOT / spec.path).read_bytes()
        assert raw == M.canonical_json_bytes(document)
        assert len(raw) == spec.size_bytes


def test_writer_emits_only_stage12581_outputs_with_same_statuses(tmp_path, monkeypatch):
    result = M.build_stage()
    out = tmp_path / "runs/local/artifacts" / M.STAGE
    summary = tmp_path / "runs/summaries" / f"{M.STAGE}.json"
    monkeypatch.setattr(M, "OUT", out)
    monkeypatch.setattr(M, "SUMMARY", summary)
    M.write_artifacts(result)
    assert sorted(path.name for path in out.iterdir()) == [
        "external_publication_bundle_manifest.json",
        "external_publication_request.json",
        "summary.json",
    ]
    manifest = json.loads((out / "external_publication_bundle_manifest.json").read_bytes())
    assert manifest["ordered_files"] == result["ordered_files"]
    assert manifest["publication_not_yet_performed"] is True
    assert manifest["external_timestamp_absent"] is True
    assert manifest["acquisition_blocked"] is True
    assert all(manifest[key] is False for key in M.FALSE_GATES)
    assert json.loads(summary.read_bytes()) == result


def test_repository_artifacts_exactly_match_fresh_in_memory_build_bytes_and_hashes():
    result = M.build_stage()
    summary_body = {key: value for key, value in result.items() if key != "summary_record_sha256"}
    assert result["summary_record_sha256"] == M.stable_hash(summary_body)
    expected = {
        M.OUT / "external_publication_bundle_manifest.json": M.bundle_manifest(result),
        M.OUT / "external_publication_request.json": result,
        M.OUT / "summary.json": result,
        M.SUMMARY: result,
    }
    for path, value in expected.items():
        expected_bytes = M.canonical_json_bytes(value)
        observed_bytes = path.read_bytes()
        assert observed_bytes == expected_bytes
        assert hashlib.sha256(observed_bytes).hexdigest() == hashlib.sha256(expected_bytes).hexdigest()
        observed = json.loads(observed_bytes)
        assert observed.get("summary_record_sha256") == result["summary_record_sha256"]
