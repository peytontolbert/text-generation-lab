import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/build_stage12629_authoritative_ledger_dry_run_authority_source_packet.py'
SPEC = importlib.util.spec_from_file_location('stage12629', SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def independent_stable_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    return hashlib.sha256(data).hexdigest()


def assert_false_boundaries(record):
    for field in (
        'implementation_ready', 'dataset_admission_allowed', 'dataset_rows_admitted', 'new_rows_admitted',
        'frontier_100m_training_dataset_ready', 'source_packet_implementation_allowed', 'source_packet_executable',
        'stage12620_allowed', 'stage12621_allowed', 'stage12622_allowed', 'stage12623_allowed', 'stage12624_allowed',
        'stage12625_allowed', 'stage12626_allowed', 'stage12627_allowed', 'stage12628_allowed', 'stage12629_allowed',
        'stage12627_authoritative_ledger_update_dry_run_only_allowed',
        'stage12628_authoritative_ledger_dry_run_authorization_review_allowed',
        'stage12629_authoritative_ledger_update_dry_run_only_allowed',
        'stage12630_allowed', 'stage12630_authoritative_ledger_update_dry_run_only_allowed',
        'vm_branch_active', 'vm_runner_implementation_allowed', 'vm_runner_implementation_ready', 'vm_runner_execution_allowed',
        'vm_runner_evidence_present', 'vm_runner_trustworthy', 'storage_root_created', 'storage_write_performed',
        'execution_performed', 'replay_trustworthy', 'raw_replay_evidence_present', 'trusted_replay_raw_evidence_present',
        'causal_transition_atoms_present', 'causal_transition_atoms_allowed', 'level3_preflight_allowed',
        'level_3_materialized', 'level_3_materialization_allowed', 'training_admission_preflight_allowed',
        'training_admission_allowed', 'training_admitted', 'training_allowed', 'training_run_allowed',
        'gpu_allocation_requested', 'cuda2_training_allowed', 'strict_eval_admitted', 'sealed_eval_admitted',
        'strict_eval_eligible', 'sealed_eval_eligible', 'admission_allowed', 'ranking_allowed', 'positive_stop',
        'authoritative_ledger_updated', 'authoritative_ledger_update_allowed', 'authoritative_ledger_dry_run_performed',
        'authoritative_ledger_dry_run_allowed', 'control_board_promoted_to_authoritative', 'control_board_promotion_allowed',
        'row_artifacts_written', 'summary_artifact_written', 'ledger_update_materialized', 'candidate_ledger_materialized',
        'candidate_rows_materialized', 'dry_run_candidate_artifacts_written', 'dry_run_authorized', 'dry_run_ready',
        'dry_run_authorization_granted', 'dry_run_authority_source_packet_present',
        'authoritative_ledger_update_dry_run_materialized',
    ):
        assert field in record
        assert record[field] is False


def test_load_stage12628_requires_exact_blocker_and_no_existing_authority_source_packet():
    loaded = stage.load_stage12628()
    summary = loaded['summary']
    review = loaded['authorization_review']
    assert summary['authorization_review_outcome'] == 'blocked'
    assert summary['dry_run_authorization_status'] == 'blocked_missing_explicit_dry_run_authority_source_packet'
    assert summary['dry_run_authority_source_packet_present'] is False
    assert summary['stage12629_authoritative_ledger_update_dry_run_only_allowed'] is False
    assert summary['stage12629_allowed'] is False
    assert review['minimum_unblock_condition'] == 'separate_explicit_dry_run_authority_source_packet_required'
    assert independent_stable_hash(review) == stage.EXPECTED_HASHES['stage12628_authorization_review']


def test_request_scope_is_preflight_only_and_not_authority():
    scope = stage.request_scope()
    assert scope['requested_future_review'] == 'stage12630_authoritative_ledger_dry_run_authority_source_packet_review_only'
    assert 'candidate_ledger_files_only_authority_source_packet' in scope['request_only_items']
    assert 'no_authoritative_ledger_replacement' in scope['required_boundaries_for_any_later_authority_packet']
    assert 'no_dataset_admission' in scope['required_boundaries_for_any_later_authority_packet']
    assert 'no_training_or_eval_admission' in scope['required_boundaries_for_any_later_authority_packet']
    assert 'independent_authority_source_packet_review' in scope['required_parent_verification_before_any_later_authority']
    assert 'creating_authority_source_packet_in_stage12629' in scope['still_forbidden']
    assert 'granting_dry_run_authorization' in scope['still_forbidden']


def test_packet_records_request_without_source_packet_or_execution_authority():
    summary, contract, private = stage.build_request_packet(stage.load_stage12628())
    assert summary['decision'] == 'DRY_RUN_AUTHORITY_SOURCE_PACKET_REQUEST_RECORDED_NO_AUTHORITY_GRANTED'
    assert summary['dry_run_authority_source_packet_request_only'] is True
    assert summary['vm_branch_remains_paused'] is True
    assert summary['dry_run_authority_source_packet_present'] is False
    assert summary['stage12629_authoritative_ledger_update_dry_run_only_allowed'] is False
    assert summary['stage12630_authoritative_ledger_update_dry_run_only_allowed'] is False
    assert summary['stage12629_allowed'] is False
    assert summary['stage12630_allowed'] is False
    assert summary['dry_run_authorized'] is False
    assert summary['dry_run_authorization_granted'] is False
    assert summary['authoritative_ledger_dry_run_allowed'] is False
    assert summary['authoritative_ledger_dry_run_performed'] is False
    assert summary['authoritative_ledger_updated'] is False
    assert summary['candidate_artifacts_written'] == 0
    assert summary['training_allowed'] is False
    assert contract['private_dry_run_authority_source_packet_request_sha256'] == independent_stable_hash(private)
    assert summary['request_scope_sha256'] == independent_stable_hash(private['request_scope'])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_packet_preserves_authoritative_count_and_conditional_candidate_only():
    summary, _contract, _private = stage.build_request_packet(stage.load_stage12628())
    assert summary['authoritative_admitted_train_support_tasks_after_request'] == 158
    assert summary['authoritative_gap_to_500_after_request'] == 342
    assert summary['conditional_candidate_count_if_later_authority_and_dry_run_pass'] == 190
    assert summary['conditional_candidate_gap_if_later_authority_and_dry_run_pass'] == 310
    assert summary['reviewed_plan_delta_total'] == 32
    assert summary['reviewed_selected_lineage_delta'] == 14
    assert summary['reviewed_direct_real_log_delta'] == 18
    assert summary['stage12418_derived_projection_countable_rows'] == 0
    assert summary['frontier_100m_training_dataset_ready'] is False


def test_build_writes_only_request_artifacts(tmp_path):
    out = tmp_path / 'artifacts' / stage.STAGE
    summary_path = tmp_path / 'summaries' / f'{stage.STAGE}.json'
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob('*') if path.is_file())
    assert emitted == [
        'contract.json',
        'digest_pointer.json',
        'private/authoritative_ledger_dry_run_authority_source_packet_request_only.json',
        'summary.json',
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / 'summary.json')


def test_generated_artifacts_match_current_request_packet():
    out = stage.OUT
    summary = read_json(out / 'summary.json')
    external = read_json(stage.SUMMARY)
    contract = read_json(out / 'contract.json')
    pointer = read_json(out / 'digest_pointer.json')
    private = read_json(out / 'private/authoritative_ledger_dry_run_authority_source_packet_request_only.json')
    assert summary == external
    assert summary['dry_run_authority_source_packet_request_only'] is True
    assert summary['dry_run_authority_source_packet_present'] is False
    assert summary['stage12630_authoritative_ledger_update_dry_run_only_allowed'] is False
    assert summary['stage12630_allowed'] is False
    assert summary['training_allowed'] is False
    assert summary['frontier_100m_training_dataset_ready'] is False
    assert summary['authoritative_admitted_train_support_tasks_after_request'] == 158
    assert summary['authoritative_gap_to_500_after_request'] == 342
    assert summary['candidate_artifacts_written'] == 0
    assert pointer['contract_sha256'] == independent_stable_hash(contract)
    assert pointer['private_dry_run_authority_source_packet_request_sha256'] == independent_stable_hash(private)
    assert pointer['request_scope_sha256'] == independent_stable_hash(private['request_scope'])
    assert summary['private_dry_run_authority_source_packet_request_sha256'] == independent_stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    forbidden = (
        '/data/', '/arxiv/', 'agentkernel_vm_replay', '/dev/', 'selector', 'raw_stream',
        'stdout.raw', 'stderr.raw', 'before_commit_oid', 'after_commit_oid', 'production_path',
        'production_patch_sha256', 'manual_executor_slot_contracts', 'slot_1.patch', 'slot_2.patch',
        'repository_root', 'patch_path', 'slot_1/', 'slot_2/', 'combined_selected_test_rows',
        'combined_train_support_rows', 'direct_verifier_log_train_support_manifest', 'direct_verifier_log_train_support_rows',
        'guardrail_scan.json', 'combined_train_support_ledger', 'jsonl', 'row_id', 'stable_lineage_key',
    )
    allowed_true = {
        'dry_run_authority_source_packet_request_only',
        'vm_branch_remains_paused',
    }
    for path in [stage.OUT / 'summary.json', stage.SUMMARY, stage.OUT / 'contract.json', stage.OUT / 'digest_pointer.json']:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
