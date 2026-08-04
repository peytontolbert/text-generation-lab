#!/usr/bin/env python3
# Build Stage12629 authoritative ledger dry-run authority source-packet request.
# This is request/preflight only. It does not create an authority packet, grant a
# dry-run gate, perform a dry run, write candidate files, update the ledger,
# admit rows, train, resume VM/replay, materialize Level-3, or authorize a successor.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = 'stage12629_authoritative_ledger_dry_run_authority_source_packet_request_only'
OUT = ROOT / 'runs/local/artifacts' / STAGE
SUMMARY = ROOT / 'runs/summaries' / f'{STAGE}.json'
S12628 = ROOT / 'runs/local/artifacts/stage12628_authoritative_ledger_dry_run_authorization_review_only'
S12628_SUMMARY = ROOT / 'runs/summaries/stage12628_authoritative_ledger_dry_run_authorization_review_only.json'

EXPECTED_HASHES = {
    'stage12628_summary': '0b84b1ee422e70057982782f52a770a50f2bd8ca3571f624d4b5d6ed47e152d0',
    'stage12628_contract': '6464d417072e4b7eb370c38b6ff763b3dbaad357b0a88136fd0f80f81319d29b',
    'stage12628_pointer': '8d0e59484db993cc29ab6c4dbd244f434548c0ba2b6ed04ecb6b4cc3da656a12',
    'stage12628_private': 'a25a345d42c4935f9a2d21b0b183a4509e1bb0fcfa2a772f94352a310908e2f3',
    'stage12628_authorization_review': '91c6c96f7afc8eee8833bbfe4593bf5cbd7c5bc0d0f7d7e3b0c343a5790f42ad',
    'stage12627_preflight_review': 'c179438a28968df23d51a0b25b0f0f00082af83f45721d499f52343eb4d9e59f',
    'stage12626_update_plan': '2ebc45d3c86e6a51d3011b8b5b95f6bb7c19823cbaa54d8815ebffea66e24f99',
    'stage12376': 'a7aa3bcae28c5741f1955d2b954744143266bb61d2e824d78343e932cc3b695e',
    'stage12417': 'c9a872e36c12888b7f3fd45218cb69aa7d75b238378368289483ba54c483721a',
}

FALSE_FIELDS = (
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
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    '/data/', '/arxiv/', 'agentkernel_vm_replay', '/dev/', 'selector', 'raw_stream',
    'stdout.raw', 'stderr.raw', 'before_commit_oid', 'after_commit_oid', 'production_path',
    'production_patch_sha256', 'manual_executor_slot_contracts', 'slot_1.patch', 'slot_2.patch',
    'repository_root', 'patch_path', 'slot_1/', 'slot_2/', 'combined_selected_test_rows',
    'combined_train_support_rows', 'direct_verifier_log_train_support_manifest', 'direct_verifier_log_train_support_rows',
    'guardrail_scan.json', 'combined_train_support_ledger', 'jsonl', 'row_id', 'stable_lineage_key',
)


class DryRunAuthoritySourcePacketRequestError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise DryRunAuthoritySourcePacketRequestError('json_object_required:' + path.name)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode('ascii') + b'\n'
    with path.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise DryRunAuthoritySourcePacketRequestError(f'{label}_gate_drift:{field}')


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise DryRunAuthoritySourcePacketRequestError(f'{label}_public_leak:{needle}')


def load_stage12628() -> dict[str, Any]:
    summary = read_json(S12628 / 'summary.json')
    external = read_json(S12628_SUMMARY)
    contract = read_json(S12628 / 'contract.json')
    pointer = read_json(S12628 / 'digest_pointer.json')
    private = read_json(S12628 / 'private/authoritative_ledger_dry_run_authorization_review_only.json')
    if summary != external:
        raise DryRunAuthoritySourcePacketRequestError('stage12628_external_summary_mismatch')
    for label, value in (
        ('stage12628_summary', summary), ('stage12628_contract', contract),
        ('stage12628_pointer', pointer), ('stage12628_private', private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise DryRunAuthoritySourcePacketRequestError('stage12628_pin_drift:' + label)
    review = private.get('dry_run_authorization_review') or {}
    if stable_hash(review) != EXPECTED_HASHES['stage12628_authorization_review']:
        raise DryRunAuthoritySourcePacketRequestError('stage12628_authorization_review_hash_drift')
    if summary.get('authorization_review_outcome') != 'blocked':
        raise DryRunAuthoritySourcePacketRequestError('stage12628_outcome_drift')
    if summary.get('dry_run_authorization_status') != 'blocked_missing_explicit_dry_run_authority_source_packet':
        raise DryRunAuthoritySourcePacketRequestError('stage12628_blocker_drift')
    if summary.get('dry_run_authority_source_packet_present') is not False:
        raise DryRunAuthoritySourcePacketRequestError('stage12628_source_packet_presence_drift')
    if summary.get('stage12629_authoritative_ledger_update_dry_run_only_allowed') is not False:
        raise DryRunAuthoritySourcePacketRequestError('stage12628_stage12629_gate_drift')
    if summary.get('stage12629_allowed') is not False:
        raise DryRunAuthoritySourcePacketRequestError('stage12628_broad_successor_gate_drift')
    if summary.get('authoritative_admitted_train_support_tasks_after_review') != 158:
        raise DryRunAuthoritySourcePacketRequestError('stage12628_authoritative_count_drift')
    if summary.get('authoritative_gap_to_500_after_review') != 342:
        raise DryRunAuthoritySourcePacketRequestError('stage12628_authoritative_gap_drift')
    if review.get('minimum_unblock_condition') != 'separate_explicit_dry_run_authority_source_packet_required':
        raise DryRunAuthoritySourcePacketRequestError('stage12628_unblock_condition_drift')
    return {'summary': summary, 'contract': contract, 'pointer': pointer, 'private': private, 'authorization_review': review}


def request_scope() -> dict[str, Any]:
    return {
        'record_type': 'stage12629_candidate_ledger_dry_run_authority_request_scope_v1',
        'requested_future_review': 'stage12630_authoritative_ledger_dry_run_authority_source_packet_review_only',
        'request_only_items': [
            'candidate_ledger_files_only_authority_source_packet',
            'candidate_summary_diff_only_authority_source_packet',
            'pinned_stage12626_plan_input_recount_contract',
            'private_supersession_merge_duplicate_manifest_contract',
        ],
        'required_boundaries_for_any_later_authority_packet': [
            'no_authoritative_ledger_replacement', 'no_authoritative_summary_replacement',
            'no_dataset_admission', 'no_training_or_eval_admission', 'no_gpu_allocation',
            'no_vm_or_replay_execution', 'no_generic_dataset_mining', 'no_unpinned_input_sources',
        ],
        'required_parent_verification_before_any_later_authority': [
            'independent_authority_source_packet_review', 'public_leak_scan',
            'forbidden_true_gate_scan', 'full_stage_regression_chain',
        ],
        'still_forbidden': [
            'creating_authority_source_packet_in_stage12629', 'granting_dry_run_authorization',
            'updating_authoritative_ledger', 'admitting_new_rows', 'training_or_eval_admission',
            'running_vm_or_replay', 'materializing_level3',
        ],
    }


def build_request_packet(stage12628: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scope = request_scope()
    private = {
        'record_type': 'stage12629_private_authoritative_ledger_dry_run_authority_source_packet_request_only_v1',
        **no_claim_fields(),
        'source_hashes': EXPECTED_HASHES,
        'source_decision': stage12628['summary']['decision'],
        'source_blocker': stage12628['summary']['dry_run_authorization_status'],
        'dry_run_authority_source_packet_request_only': True,
        'vm_branch_remains_paused': True,
        'request_scope': scope,
        'decision': 'DRY_RUN_AUTHORITY_SOURCE_PACKET_REQUEST_RECORDED_NO_AUTHORITY_GRANTED',
    }
    contract = {
        'record_type': 'stage12629_public_authoritative_ledger_dry_run_authority_source_packet_request_only_contract_v1',
        **no_claim_fields(),
        'stage12628_summary_sha256': EXPECTED_HASHES['stage12628_summary'],
        'stage12628_authorization_review_sha256': EXPECTED_HASHES['stage12628_authorization_review'],
        'stage12627_preflight_review_sha256': EXPECTED_HASHES['stage12627_preflight_review'],
        'stage12626_update_plan_sha256': EXPECTED_HASHES['stage12626_update_plan'],
        'stage12376_summary_sha256': EXPECTED_HASHES['stage12376'],
        'stage12417_summary_sha256': EXPECTED_HASHES['stage12417'],
        'dry_run_authority_source_packet_request_only': True,
        'request_scope_sha256': stable_hash(scope),
        'private_dry_run_authority_source_packet_request_sha256': stable_hash(private),
        'vm_branch_remains_paused': True,
        'claim_boundary': {
            'request': 'future_candidate_ledger_dry_run_authority_source_packet_only',
            'authority': 'not_granted',
            'dry_run_execution_now': 'not_performed',
            'authoritative_ledger_update': 'not_authorized',
            'new_admission': 'not_authorized',
            'training': 'not_authorized',
            'vm': 'paused_not_used_for_request',
            'replay': 'not_executed',
            'level3': 'not_materialized',
        },
    }
    summary = {
        'record_type': 'stage12629_public_authoritative_ledger_dry_run_authority_source_packet_request_only_summary_v1',
        **no_claim_fields(),
        'stage': STAGE,
        'decision': 'DRY_RUN_AUTHORITY_SOURCE_PACKET_REQUEST_RECORDED_NO_AUTHORITY_GRANTED',
        'stage12628_summary_sha256': EXPECTED_HASHES['stage12628_summary'],
        'stage12628_authorization_review_sha256': EXPECTED_HASHES['stage12628_authorization_review'],
        'stage12627_preflight_review_sha256': EXPECTED_HASHES['stage12627_preflight_review'],
        'stage12626_update_plan_sha256': EXPECTED_HASHES['stage12626_update_plan'],
        'stage12376_summary_sha256': EXPECTED_HASHES['stage12376'],
        'stage12417_summary_sha256': EXPECTED_HASHES['stage12417'],
        'dry_run_authority_source_packet_request_only': True,
        'request_scope_sha256': stable_hash(scope),
        'private_dry_run_authority_source_packet_request_sha256': stable_hash(private),
        'vm_branch_remains_paused': True,
        'authoritative_admitted_train_support_tasks_after_request': 158,
        'authoritative_gap_to_500_after_request': 342,
        'conditional_candidate_count_if_later_authority_and_dry_run_pass': 190,
        'conditional_candidate_gap_if_later_authority_and_dry_run_pass': 310,
        'reviewed_plan_delta_total': 32,
        'reviewed_selected_lineage_delta': 14,
        'reviewed_direct_real_log_delta': 18,
        'stage12418_derived_projection_countable_rows': 0,
        'candidate_artifacts_written': 0,
        'summary_artifacts_updated': 0,
        'frontier_100m_training_dataset_ready': False,
        'downstream_blockers': [
            'explicit_dry_run_authority_source_packet_still_absent',
            'dry_run_authorization_not_granted',
            'candidate_ledger_dry_run_not_materialized',
            'candidate_ledger_artifacts_not_written',
            'authoritative_ledger_not_updated_in_stage12629',
            'new_train_support_rows_not_admitted',
            'authoritative_gap_still_342',
            'training_admission_forbidden',
        ],
    }
    for label, record in (('summary', summary), ('contract', contract)):
        check_false(record, 'stage12629_' + label)
        assert_public_sanitized(record, 'stage12629_' + label)
    check_false(private, 'stage12629_private')
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12628 = load_stage12628()
    summary, contract, private = build_request_packet(stage12628)
    pointer = {
        'record_type': 'stage12629_public_private_authoritative_ledger_dry_run_authority_source_packet_request_only_pointer_v1',
        **no_claim_fields(),
        'stage12628_summary_sha256': EXPECTED_HASHES['stage12628_summary'],
        'contract_sha256': stable_hash(contract),
        'private_dry_run_authority_source_packet_request_sha256': stable_hash(private),
        'request_scope_sha256': stable_hash(private['request_scope']),
        'dry_run_authority_source_packet_request_only': True,
        'vm_branch_remains_paused': True,
    }
    check_false(pointer, 'stage12629_pointer')
    assert_public_sanitized(pointer, 'stage12629_pointer')
    write_json(out / 'contract.json', contract)
    write_json(out / 'digest_pointer.json', pointer)
    write_json(out / 'private/authoritative_ledger_dry_run_authority_source_packet_request_only.json', private)
    write_json(out / 'summary.json', summary)
    write_json(summary_path, summary)
    return summary


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
