from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12579_bounded_source_native_replacement_acquisition.py"
SPEC = importlib.util.spec_from_file_location("stage12579", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def _replace(row, **changes):
    values = M.asdict(row)
    values.update(changes)
    return M.AllowlistedSource(**values)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Stage12579 Test")
    _git(repo, "config", "user.email", "stage12579@example.test")
    _git(repo, "remote", "add", "origin", "https://github.com/example/project.git")
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "src/lib.rs").write_text("pub fn value() -> u8 { 1 }\n", encoding="utf-8")
    (repo / "tests/value.rs").write_text("#[test] fn value() {}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "source and test")
    return repo, _git(repo, "rev-parse", "HEAD")


@pytest.fixture(scope="module")
def default_result():
    return M.build_stage()


def test_importlib_loader_without_sys_modules_registration_is_supported():
    assert "stage12579" not in sys.modules
    assert len(M.CANONICAL_ALLOWLIST) == 8


def test_default_is_zero_candidate_pure_request_builder(default_result):
    assert default_result["decision"] == "blocked_fail_closed_zero_credit"
    assert default_result["candidate_count"] == 0
    assert default_result["network_clone_performed"] is False
    assert default_result["execution_performed"] is False
    assert default_result["execution_receipt_emitted"] is False
    assert all(default_result[field] is False for field in M.DENY_FIELDS)


def test_hostile_complete_closure_and_forged_stage_record_are_non_authoritative():
    canonical = M.build_authority_closure()
    hostile = {**canonical, "complete": True}
    forged_record = {
        "stage": "stage12578_prospective_source_acquisition_and_structural_preoutcome_seal",
        "summary_record_sha256": M.STAGE12578_RECORD_SHA256,
        "complete": True,
    }
    result = M.build_stage(
        stage12578_digest=M.STAGE12578_FILE_SHA256,
        stage12578_record=forged_record,
        closure=hostile,
    )
    assert result["candidate_count"] == 0
    assert result["exact_canonical_authority_binding"] is False
    assert result["exact_canonical_stage12578_binding"] is False
    assert "caller_authority_closure_non_authoritative" in result["blocking_reasons"]
    assert "stage12578_caller_record_non_authoritative" in result["blocking_reasons"]


def test_requested_commits_are_diagnostic_and_have_no_preoutcome_authority(default_result):
    requests = default_result["acquisition_requests"]
    rust = [row for row in requests if row["language"] == "rust"]
    assert len(rust) == 4
    assert all(row["requested_commit_provenance"] == "diagnostic_self_attested" for row in rust)
    assert all(row["requested_commit_authoritative"] is False for row in rust)
    assert all(row["preoutcome_authority"] is False for row in requests)
    assert all("preoutcome_commit_authority_absent" in row["reason_codes"] for row in requests)
    assert all(
        f"{row['source_id']}:preoutcome_commit_authority_absent"
        in default_result["blocking_reasons"]
        for row in requests
    )


def test_historical_aliases_and_family_aware_collisions_are_closed():
    expected = {"perftree", "mcp", "mcpagent", "lastmileaimcpagent", "openclaw"}
    assert expected <= set(M.HISTORICAL_FAMILY_ALIASES)
    mcp_agent = M.family_aliases("https://github.com/lastmile-ai/mcp-agent")
    assert {"mcpagent", "lastmileaimcpagent"} <= mcp_agent
    authority = {
        alias
        for historical in M.HISTORICAL_FAMILY_ALIASES
        for alias in M.family_aliases(historical)
    }
    assert M.family_aliases("git@github.com:lastmile-ai/mcp-agent.git") & authority
    assert M.family_aliases("https://github.com/example/perftree") & authority
    assert M.family_aliases("https://github.com/openclaw/openclaw") & authority


def test_request_manifest_is_exactly_four_rust_and_four_independent_web(default_result):
    requests = default_result["acquisition_requests"]
    assert len(requests) == 8
    assert Counter(row["language"] for row in requests) == Counter(
        {"rust": 4, "web_js_ts_html": 4}
    )
    web = [row for row in requests if row["language"] == "web_js_ts_html"]
    assert {row["source_id"] for row in web} == {"lodash", "chalk", "pnpm", "ms"}
    assert not {row["source_id"] for row in web} & {
        "bddy_website", "bddy_app", "bddy_desktop", "bddy_api"
    }
    assert len({M.web_family_key(row) for row in M.CANONICAL_ALLOWLIST if row.language == "web_js_ts_html"}) == 4
    assert all(row["authority_family_overlap"] is False for row in web)
    assert all(row["independent_web_quota_eligible"] is True for row in web)
    assert all("family_normalized_authority_overlap" not in row["reason_codes"] for row in web)
    assert all(row["requested_commit"] is None for row in web)
    assert all(row["requested_commit_authoritative"] is False for row in web)
    assert all(row["preoutcome_authority"] is False for row in web)
    assert all(row["commands"] == [] for row in web)
    assert all(row["execution_eligible"] is False for row in web)
    assert all("independent_commit_pin_missing" in row["reason_codes"] for row in web)
    assert default_result["acquisition_request_count_by_language"] == {
        "rust": 4,
        "web_js_ts_html": 4,
    }
    assert default_result["independent_web_request_quota_count"] == 4
    assert "independent_web_request_quota_not_met" not in default_result["blocking_reasons"]


def test_language_quota_and_invented_web_hash_are_rejected():
    wrong_language = list(M.CANONICAL_ALLOWLIST)
    wrong_language[0] = _replace(wrong_language[0], language="web_js_ts_html")
    blockers = M.validate_allowlist(wrong_language)
    assert "caller_allowlist_override_rejected" in blockers
    assert "request_language_quota_mismatch" in blockers

    invented_web = list(M.CANONICAL_ALLOWLIST)
    invented_web[4] = _replace(invented_web[4], requested_commit="a" * 40)
    blockers = M.validate_allowlist(invented_web)
    assert "lodash:unverified_web_commit_pin_rejected" in blockers


def test_overlapped_missing_commit_records_overlap_and_cannot_fill_web_quota():
    authority = M.build_authority_closure()["family_aliases"]
    overlapped = M.AllowlistedSource(
        "mcpagent",
        "https://github.com/lastmile-ai/mcp-agent",
        None,
        "/data/repositories/mcp-agent",
        "web_js_ts_html",
    )
    request = M.acquisition_request(overlapped, authority)
    assert request["requested_commit"] is None
    assert request["requested_commit_authoritative"] is False
    assert request["preoutcome_authority"] is False
    assert request["authority_family_overlap"] is True
    assert request["independent_web_quota_eligible"] is False
    assert "family_normalized_authority_overlap" in request["reason_codes"]
    assert "independent_commit_pin_missing" in request["reason_codes"]

    rows = list(M.CANONICAL_ALLOWLIST)
    rows[4] = overlapped
    blockers = M.validate_independent_web_quota(rows, authority)
    assert "independent_web_request_quota_not_met" in blockers


def test_injected_records_are_non_authoritative_and_nested_outcomes_rejected():
    injected = {"active_protected": [{"nested": {"payload": [{"model_score": 1.0}]}}]}
    closure = M.build_authority_closure(
        file_digests=dict(M.UNIVERSE_PINS),
        records=injected,
    )
    assert closure["complete"] is False
    assert "injected_authority_records_non_authoritative" in closure["blocking_reasons"]
    assert "injected_authority_records_forbidden_fields" in closure["blocking_reasons"]
    assert M.forbidden_paths({"outer": [{"inner": {"outcome": "pass"}}]}) == [
        "$.outer[0].inner.outcome"
    ]


def test_exact_commit_remote_tree_source_test_and_diff_are_observed(tmp_path):
    repo, commit = _repo(tmp_path)
    row = M.AllowlistedSource(
        "project",
        "https://github.com/example/project",
        commit,
        str(repo),
    )
    observation = M.inspect_checkout(row)
    assert observation["requested_commit"] == commit
    assert len(observation["tree_oid"]) == 40
    assert observation["tracked_source_blob_count"] == 2
    assert observation["tracked_test_blob_count"] == 1
    assert observation["clean_committed_content"] is True
    assert observation["task_diff_evidence_ready"] is True
    assert set(observation["preoutcome_stratum_bindings"]) == set(M.STRATA)


def test_wrong_commit_dirty_source_and_remote_fail_closed(tmp_path):
    repo, commit = _repo(tmp_path)
    wrong = M.AllowlistedSource(
        "project",
        "https://github.com/example/project",
        "0" * 40,
        str(repo),
    )
    with pytest.raises(ValueError, match="exact_requested_commit_mismatch"):
        M.inspect_checkout(wrong)

    bad_remote = _replace(wrong, requested_commit=commit, canonical_remote="https://github.com/example/other")
    with pytest.raises(ValueError, match="canonical_remote_mismatch"):
        M.inspect_checkout(bad_remote)

    (repo / "src/lib.rs").write_text("mutated\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dirty_tree"):
        M.inspect_checkout(_replace(wrong, requested_commit=commit))


def test_third_observation_mutation_blocks_before_emission(monkeypatch, tmp_path):
    rows = tuple(
        _replace(row, checkout=str(tmp_path / row.source_id))
        for row in M.CANONICAL_ALLOWLIST
    )
    for row in rows:
        if row.language == "rust":
            Path(row.checkout).mkdir()
    monkeypatch.setattr(M, "CANONICAL_ALLOWLIST", rows)
    monkeypatch.setattr(M, "ALLOWLIST", rows)
    monkeypatch.setattr(M, "ALLOWLIST_SHA256", M.stable_hash([M.asdict(row) for row in rows]))

    calls: Counter[str] = Counter()

    def observation(row):
        calls[row.source_id] += 1
        digest = "changed" if row.source_id == "serde" and calls[row.source_id] == 3 else "stable"
        return {
            "source_id": row.source_id,
            "canonical_remote": row.canonical_remote,
            "requested_commit": row.requested_commit,
            "tree_oid": "b" * 40,
            "tracked_source_blob_count": 2,
            "tracked_test_blob_count": 1,
            "tracked_source_bytes": 10,
            "tracked_blob_set_sha256": "c" * 64,
            "clean_committed_content": True,
            "task_diff_evidence_ready": True,
            "task_diff_path_set_sha256": "d" * 64,
            "preoutcome_four_stratum_binding_ready": True,
            "preoutcome_stratum_bindings": {key: "e" * 64 for key in M.STRATA},
            "identity_tokens": set(),
            "family_aliases": set(),
            "observation_sha256": digest,
        }

    monkeypatch.setattr(M, "inspect_checkout", observation)
    result = M.build_stage(allowlist=rows)
    assert result["candidate_count"] == 0
    assert all(calls[row.source_id] == 3 for row in rows if row.language == "rust")
    serde = next(row for row in result["diagnostics"] if row["source_id"] == "serde")
    assert "source_mutated_before_emission" in serde["reason_codes"]
    assert "serde:source_mutated_before_emission" in result["blocking_reasons"]


def test_executor_requires_exact_generated_hash_and_writes_separate_receipt(
    monkeypatch,
    tmp_path,
    default_result,
):
    artifact = tmp_path / "acquisition_requests.json"
    receipt_path = tmp_path / "execution_receipt.json"
    M.write_json(artifact, M.canonical_request_artifact())
    request = M.canonical_request_artifact()["requests"][0]
    calls = []

    def completed(command, *, check):
        calls.append(command)
        assert check is True
        return SimpleNamespace(returncode=0)

    with pytest.raises(PermissionError, match="acquisition_executor_disabled"):
        M.execute_acquisition(
            request["request_sha256"],
            request_artifact=artifact,
            receipt_path=receipt_path,
        )
    assert calls == []
    assert not receipt_path.exists()

    with pytest.raises(ValueError, match="exact_generated_request_hash_required"):
        M.execute_acquisition(
            "0" * 64,
            enabled=True,
            request_artifact=artifact,
            receipt_path=receipt_path,
        )
    assert calls == []

    class MissingCheckout:
        def exists(self):
            return False

    monkeypatch.setattr(M, "Path", lambda _value: MissingCheckout())
    monkeypatch.setattr(M.subprocess, "run", completed)
    receipt = M.execute_acquisition(
        request["request_sha256"],
        enabled=True,
        request_artifact=artifact,
        receipt_path=receipt_path,
    )
    persisted = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt == persisted
    assert receipt["status"] == "completed"
    assert receipt["execution_occurred"] is True
    assert receipt["network_command_executed"] is True
    assert receipt["command_count_attempted"] == 3
    assert receipt["command_count_succeeded"] == 3
    assert len(calls) == 3
    assert default_result["execution_performed"] is False
    assert default_result["execution_receipt_emitted"] is False


def test_executor_rejects_tampered_generated_artifact(tmp_path):
    artifact = M.canonical_request_artifact()
    artifact["requests"][0]["candidate"] = True
    path = tmp_path / "tampered.json"
    M.write_json(path, artifact)
    with pytest.raises(ValueError, match="generated_request_artifact_mismatch"):
        M.execute_acquisition("a" * 64, enabled=True, request_artifact=path)
