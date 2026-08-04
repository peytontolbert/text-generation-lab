import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12620_independent_source_packet_static_review.py"
SPEC = importlib.util.spec_from_file_location("stage12620", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def independent_stable_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "source_packet_implementation_allowed", "source_packet_executable",
        "stage12595_allowed", "stage12613_allowed", "stage12614_allowed", "stage12615_allowed",
        "stage12616_allowed", "stage12617_allowed", "stage12618_allowed", "stage12619_allowed",
        "stage12620_allowed", "stage12621_allowed", "execution_performed", "replay_trustworthy",
        "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
        "external_bwrap_execution_evidence_present", "alternate_replay_evidence_present",
        "alternate_replay_trustworthy", "vm_runner_implementation_ready", "vm_runner_execution_allowed",
        "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
        "host_workspace_mounted_in_guest", "host_volume_mounted_in_guest", "guest_network_enabled",
        "guest_gpu_enabled", "causal_transition_atoms_present", "causal_transition_atoms_materialized",
        "causal_transition_atoms_allowed", "causally_committed_pre_outcome_candidate_set_present",
        "observed_stop_continue_decision_provenance_present", "level3_preflight_allowed",
        "level_3_materialized", "level_3_materialization_allowed", "training_admission_preflight_allowed",
        "training_admission_allowed", "training_admitted", "training_allowed", "training_run_allowed",
        "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
    ):
        assert field in record
        assert record[field] is False


def test_load_stage12619_requires_static_review_only_gate():
    loaded = stage.load_stage12619()
    summary = loaded["summary"]
    assert summary["decision"] == "NON_EXECUTABLE_SOURCE_PACKET_MATERIALIZED_STATIC_REVIEW_REQUIRED"
    assert summary["source_packet_materialized"] is True
    assert summary["stage12620_allowed"] is False
    assert summary["stage12620_static_review_only_allowed"] is True
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["source_packet_executable"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False


def test_review_source_packet_confirms_file_set_and_static_constraints():
    report = stage.review_source_packet()
    assert report["reviewed_file_count"] == 12
    assert report["json_only_confirmed"] is True
    assert report["non_executable_modes_confirmed"] is True
    assert report["forbidden_token_scan_passed"] is True
    assert report["manifest_module_specs_confirmed"] is True
    assert report["manifest_static_tests_confirmed"] is True
    assert set(report["reviewed_file_hashes"]) == {
        "source_packet/manifest.json",
        "source_packet/static_review_tests.json",
        *[f"source_packet/module_specs/{name}.json" for name in stage.EXPECTED_MODULES],
    }


def test_static_review_passes_without_authorizing_implementation_execution_training():
    loaded = stage.load_stage12619()
    summary, contract, private = stage.build_review_packet(loaded)
    assert summary["decision"] == "INDEPENDENT_SOURCE_PACKET_STATIC_REVIEW_PASSED_IMPLEMENTATION_AUTHORIZATION_STILL_BLOCKED"
    assert summary["independent_source_packet_static_review_passed"] is True
    assert summary["stage12620_allowed"] is False
    assert summary["stage12620_static_review_only_allowed"] is True
    assert summary["source_packet_json_only_confirmed"] is True
    assert summary["source_packet_non_executable_confirmed"] is True
    assert summary["source_packet_forbidden_token_scan_passed"] is True
    assert summary["source_packet_public_leak_scan_passed"] is True
    assert summary["stage12621_source_implementation_authorization_review_only_allowed"] is True
    assert summary["stage12621_allowed"] is False
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["source_packet_executable"] is False
    assert summary["implementation_ready"] is False
    assert summary["vm_runner_implementation_ready"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["storage_write_performed"] is False
    assert summary["execution_performed"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["level_3_materialized"] is False
    assert summary["training_allowed"] is False
    assert contract["private_source_packet_static_review_sha256"] == independent_stable_hash(private)
    assert summary["source_packet_static_review_report_sha256"] == independent_stable_hash(private["source_packet_static_review_report"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/independent_source_packet_static_review.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_static_review():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/independent_source_packet_static_review.json")
    assert summary == external
    assert summary["independent_source_packet_static_review_passed"] is True
    assert summary["stage12620_allowed"] is False
    assert summary["stage12620_static_review_only_allowed"] is True
    assert summary["stage12621_source_implementation_authorization_review_only_allowed"] is True
    assert summary["stage12621_allowed"] is False
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["source_packet_executable"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_source_packet_static_review_sha256"] == independent_stable_hash(private)
    assert summary["private_source_packet_static_review_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_public_artifacts_have_no_private_leak_literals():
    forbidden = (
        "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
        "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
        "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
        "repository_root", "patch_path", "slot_1/", "slot_2/",
    )
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        encoded = json.dumps(read_json(path), sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]


def test_independent_true_gate_scan_allows_only_review_markers():
    allowed = {
        "independent_source_packet_static_review_passed",
        "stage12620_static_review_only_allowed",
        "source_packet_json_only_confirmed",
        "source_packet_non_executable_confirmed",
        "source_packet_forbidden_token_scan_passed",
        "source_packet_public_leak_scan_passed",
        "stage12621_source_implementation_authorization_review_only_allowed",
    }
    for path in [
        stage.OUT / "summary.json",
        stage.SUMMARY,
        stage.OUT / "contract.json",
        stage.OUT / "digest_pointer.json",
        stage.OUT / "private/independent_source_packet_static_review.json",
    ]:
        record = read_json(path)
        assert {key for key, value in record.items() if value is True} == allowed
        assert record["stage12621_allowed"] is False
        assert record["source_packet_implementation_allowed"] is False
        assert record["vm_runner_execution_allowed"] is False
        assert record["training_allowed"] is False
