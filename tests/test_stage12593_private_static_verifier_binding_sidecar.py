import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12593_private_static_verifier_binding_sidecar.py"
SPEC = importlib.util.spec_from_file_location("stage12593", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fake_binding(candidate_ref):
    payload = {
        "schema": "stage12593_canonical_immutable_binding_payload_v2",
        "repository": {
            "path": f"/private/repos/{candidate_ref}",
            "name": f"private-repo-{candidate_ref}",
            "before_commit_oid": "a" * 40,
            "after_commit_oid": "b" * 40,
        },
        "production_patch": {"path": "private/production.py", "sha256": "c" * 64},
        "frozen_tests": {"manifest_sha256": "d" * 64},
        "fixture": {"source_path": "private/test_source.py", "sha256": "e" * 64},
        "selector": "/private/fixture.py::TestFocused::test_exact",
        "expected_node_ids": ["/private/fixture.py::TestFocused::test_exact"],
        "expected_node_count": 1,
        "invocation": {
            "argv": ["/private/python", "-m", "pytest"],
            "cwd": "/private/worktree",
            "environment": {"PYTHONHASHSEED": "0"},
            "namespace_argv": ["bwrap", "--unshare-net"],
        },
        "namespace_clearance": {"clear": True},
    }
    binding_ref = stage.opaque_ref("binding", payload)
    return {
        "record_type": "stage12593_private_static_verifier_binding_v2",
        "candidate_ref": candidate_ref,
        "binding_ref": binding_ref,
        "binding_payload_sha256": stage.stable_hash(payload),
        "binding_payload": payload,
        "blockers": [],
        "static_binding_ready": True,
        "execution_request_ready": False,
        "request_ready": False,
        **stage.no_claim_fields(),
    }


def configure_build(monkeypatch, tmp_path, make_binding):
    out = tmp_path / "artifacts" / stage.STAGE
    summary = tmp_path / "summaries" / f"{stage.STAGE}.json"
    universe = tmp_path / "static_universe.jsonl"
    universe.write_text("".join(json.dumps({"candidate_id": pair}) + "\n" for pair in stage.PAIR_IDS))
    monkeypatch.setattr(stage, "OUT", out)
    monkeypatch.setattr(stage, "SUMMARY", summary)
    monkeypatch.setattr(stage, "S91_UNIVERSE", universe)
    monkeypatch.setattr(stage, "namespace_input_pins", lambda: {"manifest_sha256": "f" * 64})
    monkeypatch.setattr(stage, "namespace_data", lambda: (set(), set(), {}, lambda _, value: value))
    monkeypatch.setattr(stage, "make_binding", make_binding)
    return out, summary


def assert_no_authority(record):
    assert record["candidate_use_scope"] == "development_train_support_only"
    assert record["strict_eval_eligible"] is False
    assert record["sealed_eval_eligible"] is False
    for field in (
        "authorizes_execution",
        "execution_performed",
        "execution_allowed",
        "admission_allowed",
        "training_allowed",
        "ranking_allowed",
        "positive_stop",
    ):
        assert record[field] is False


def test_exact_class_selector_preserves_full_expected_method_list():
    source = b"""
class TestFocused:
    def test_first(self): pass
    async def test_second(self): pass
"""
    assert stage.node_ids(
        source, "/fixture.py", "TestFocused", ("test_first", "test_second")
    ) == [
        "/fixture.py::TestFocused::test_first",
        "/fixture.py::TestFocused::test_second",
    ]
    with pytest.raises(stage.GateError, match="static_node_manifest_drift"):
        stage.node_ids(source, "/fixture.py", "TestFocused", ("test_first",))


def test_exact_method_selector_filters_before_manifest_comparison():
    source = b"""
class TestFocused:
    def test_other(self): pass
    def test_exact(self): pass
    def test_last(self): pass
"""
    assert stage.node_ids(
        source, "/fixture.py", "TestFocused::test_exact", ("test_exact",)
    ) == ["/fixture.py::TestFocused::test_exact"]
    with pytest.raises(stage.GateError, match="selected_method_drift"):
        stage.node_ids(source, "/fixture.py", "TestFocused::test_missing", ("test_missing",))
    with pytest.raises(stage.GateError, match="selected_method_drift"):
        stage.node_ids(source, "/fixture.py", "TestFocused::test_exact", ("test_other",))
    duplicate = b"""
class TestFocused:
    def test_exact(self): pass
    def test_exact(self): pass
"""
    with pytest.raises(stage.GateError, match="selected_method_drift"):
        stage.node_ids(duplicate, "/fixture.py", "TestFocused::test_exact", ("test_exact",))


def test_real_networkx_singleton_and_pytest_class_node_manifest():
    rows = {}
    for candidate_ref in stage.PAIR_IDS:
        spec = stage.PRIVATE_SPECS[candidate_ref]
        repo = stage.REPOSITORY_BASE / spec["repo_name"]
        _, _, oid = stage.entry(repo, spec["after"], spec["test"])
        fixture = f"/fixture/{Path(spec['test']).name}"
        rows[candidate_ref] = stage.node_ids(
            stage.blob(repo, oid), fixture, spec["selector"], spec["methods"]
        )
    assert rows[stage.PAIR_IDS[1]] == [
        "/fixture/test_pajek.py::TestPajek::test_quotes_and_backslashes_roundtrip"
    ]
    assert [node.rsplit("::", 1)[1] for node in rows[stage.PAIR_IDS[0]]] == list(
        stage.PRIVATE_SPECS[stage.PAIR_IDS[0]]["methods"]
    )


def test_v2_protocol_is_nonexecuting_and_exactly_bound():
    binding = fake_binding(stage.PAIR_IDS[0])
    protocol = stage.protocol_rows(binding)
    assert [row["order"] for row in protocol] == list(range(1, 20))
    assert [row["action"] for row in protocol if row["action"].startswith("run_")] == [
        "run_initial_verifier",
        "run_patched_verifier",
        "run_final_verifier",
    ]
    assert all(row["binding_ref"] == binding["binding_ref"] for row in protocol)
    runs = [row for row in protocol if row["action"].startswith("run_")]
    assert [row["classification"] for row in runs] == [
        "EXPECTED_BEHAVIORAL_FAILURE",
        "PASS",
        "EXPECTED_BEHAVIORAL_FAILURE",
    ]
    assert all(row["expected_node_count"] == 1 for row in runs)


def test_sibling_gate_error_preserves_static_binding_and_publishes_atomically(monkeypatch, tmp_path):
    calls = []
    input_snapshots = {}

    def make_binding(candidate_ref, source, spec, namespace, pins):
        calls.append(candidate_ref)
        assert not stage.OUT.exists()
        input_snapshots[candidate_ref] = (
            copy.deepcopy(source), copy.deepcopy(spec), copy.deepcopy(namespace), copy.deepcopy(pins)
        )
        if candidate_ref == stage.PAIR_IDS[1]:
            raise stage.GateError("candidate_local_failure:private detail")
        return fake_binding(candidate_ref)

    out, summary_path = configure_build(monkeypatch, tmp_path, make_binding)
    specs_before = copy.deepcopy(stage.PRIVATE_SPECS)
    summary = stage.build()

    assert calls == list(stage.PAIR_IDS)
    assert stage.PRIVATE_SPECS == specs_before
    assert summary_path.is_file() and out.is_dir()
    assert summary["decision"] == "BLOCKED_TRUSTED_RUNNER_REQUIRED"
    assert summary["static_binding_ready_count"] == 1
    assert summary["execution_request_ready_count"] == 0
    assert summary["execution_request_ready_candidate_refs"] == []
    assert not (out / "execution_requests.jsonl").exists()
    assert len(read_jsonl(out / "nonexecuting_replay_blueprints.jsonl")) == 1
    private = read_jsonl(out / "private/verifier_binding_sidecar.jsonl")
    assert [row["candidate_ref"] for row in private] == list(stage.PAIR_IDS)
    assert private[0]["static_binding_ready"] is True
    assert private[1]["record_type"] == "stage12593_private_blocked_candidate_v2"
    for candidate_ref, snapshot in input_snapshots.items():
        assert snapshot[0] == {"candidate_id": candidate_ref}
        assert snapshot[1] == stage.PRIVATE_SPECS[candidate_ref]
        assert snapshot[3] == {"manifest_sha256": "f" * 64}


def test_production_build_shape_forces_zero_execution_readiness(monkeypatch, tmp_path):
    out, _ = configure_build(
        monkeypatch, tmp_path, lambda candidate_ref, *_: fake_binding(candidate_ref)
    )
    out.mkdir(parents=True)
    stale = out / "legacy_v1.json"
    stale.write_text('{"record_type":"stage12593_legacy_v1"}\n')
    summary = stage.build()
    private = read_jsonl(out / "private/verifier_binding_sidecar.jsonl")
    blueprints = read_jsonl(out / "nonexecuting_replay_blueprints.jsonl")
    blocked = read_jsonl(out / "blocked_candidates.jsonl")
    contract = json.loads((out / "blueprint_contract.json").read_text())

    assert summary["decision"] == "BLOCKED_TRUSTED_RUNNER_REQUIRED"
    assert summary["static_binding_ready_count"] == 2
    assert summary["execution_request_ready_count"] == 0
    assert summary["nonexecuting_replay_blueprint_count"] == 2
    assert contract["record_type"] == "stage12593_public_nonexecuting_blueprint_contract_v2"
    assert contract["execution_request_ready_count"] == 0
    assert len(private) == len(blueprints) == len(blocked) == 2
    assert not stale.exists()
    assert not (out / "execution_requests.jsonl").exists()
    for blocker in stage.TRUSTED_RUNNER_BLOCKERS:
        assert summary["blocker_counts"][blocker] == 2
    for row in private + blueprints + blocked + [contract, summary]:
        assert row["execution_request_ready"] is False if "execution_request_ready" in row else True
        assert_no_authority(row)


def test_public_private_leak_separation(monkeypatch, tmp_path):
    out, _ = configure_build(
        monkeypatch, tmp_path, lambda candidate_ref, *_: fake_binding(candidate_ref)
    )
    stage.build()
    private = read_jsonl(out / "private/verifier_binding_sidecar.jsonl")
    public = {
        "blueprints": read_jsonl(out / "nonexecuting_replay_blueprints.jsonl"),
        "blocked": read_jsonl(out / "blocked_candidates.jsonl"),
        "contract": json.loads((out / "blueprint_contract.json").read_text()),
        "summary": json.loads((out / "summary.json").read_text()),
    }
    assert stage.public_leaks(public, private) == []
    rendered = json.dumps(public, sort_keys=True)
    assert "/private/" not in rendered
    assert "private-repo-" not in rendered
    report = json.loads((out / "public_leak_scan.json").read_text())
    assert report["passed"] is True and report["leak_count"] == 0
    assert_no_authority(report)


def test_fabricated_structurally_valid_attestation_cannot_authorize():
    binding = fake_binding(stage.PAIR_IDS[0])
    payload = binding["binding_payload"]
    fingerprint = "1" * 64
    node_ids = payload["expected_node_ids"]
    phases = []
    for name in ("initial", "patched", "final"):
        phases.append({
            "name": name,
            "pytest_exit_code": stage.OUTCOMES[name][0],
            "classification": stage.OUTCOMES[name][1],
            "node_ids": node_ids,
            "node_count": 1,
            "normalized_failure_fingerprint": None if name == "patched" else fingerprint,
        })
    integrity = [
        {
            "event": row["action"],
            "fixture_sha256": payload["fixture"]["sha256"],
            "test_manifest_sha256": payload["frozen_tests"]["manifest_sha256"],
        }
        for row in stage.protocol_rows(binding)
        if row["action"].startswith("integrity_")
    ]
    attestation = {
        "binding_ref": binding["binding_ref"],
        "argv": payload["invocation"]["argv"],
        "cwd": payload["invocation"]["cwd"],
        "environment": payload["invocation"]["environment"],
        "clear_environment": True,
        "namespace_argv": payload["invocation"]["namespace_argv"],
        "fixture_sha256": payload["fixture"]["sha256"],
        "test_manifest_sha256": payload["frozen_tests"]["manifest_sha256"],
        "production_patch_sha256": payload["production_patch"]["sha256"],
        "node_ids": node_ids,
        "node_count": 1,
        "phases": phases,
        "integrity_checks": integrity,
        "initial_filesystem_digest": "2" * 64,
        "final_filesystem_digest": "2" * 64,
        "authorizes_execution": True,
        "admission_allowed": True,
        "training_allowed": True,
    }
    result = stage.validate_replay_attestation_structure(binding, attestation)
    assert result["structurally_valid"] is True
    assert result["structural_errors"] == []
    assert result["record_type"] == "stage12593_non_authoritative_attestation_structure_v2"
    assert_no_authority(result)
