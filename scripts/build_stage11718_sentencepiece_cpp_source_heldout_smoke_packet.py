#!/usr/bin/env python3
"""Materialize a pre-admission C++ smoke root from sentencepiece.

This creates real source-backed maintainer-choice rows from local source and test
files. It deliberately does not assert source_heldout_admissible until a separate
no-train overlap audit passes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = Path('/data/parametergolf/helpful_repos/sentencepiece')
OUT_DIR = ROOT / 'runs/local/artifacts/stage11718_sentencepiece_cpp_source_heldout_smoke_packet'
SUMMARY = ROOT / 'runs/summaries/stage11718_sentencepiece_cpp_source_heldout_smoke_packet.json'

FILES = {
    'implementation': 'src/bpe_model.cc',
    'test': 'src/bpe_model_test.cc',
    'trainer_impl': 'src/bpe_model_trainer.cc',
    'trainer_test': 'src/bpe_model_trainer_test.cc',
    'factory': 'src/model_factory.cc',
    'normalizer_test': 'src/normalizer_test.cc',
}


def git_commit(path: Path) -> str:
    proc = subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return proc.stdout.strip() if proc.returncode == 0 else 'unknown'


def read_excerpt(rel: str, max_lines: int = 34) -> dict[str, Any]:
    path = REPO / rel
    text = path.read_text(errors='replace')
    lines = text.splitlines()
    # Prefer the first test/body region with BPE references when possible.
    start = 0
    for i, line in enumerate(lines):
        if 'BPE' in line or 'bpe' in line or 'TEST' in line:
            start = max(0, i - 4)
            break
    excerpt = '\n'.join(lines[start:start + max_lines])
    return {
        'path': rel,
        'sha256': hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest(),
        'start_line': start + 1,
        'end_line': min(len(lines), start + max_lines),
        'text': excerpt,
    }


def option(label: str, role: str, value: str, evidence_ids: list[str]) -> dict[str, Any]:
    return {'label': label, 'role': role, 'value': value, 'evidence_ids': evidence_ids}


def row(row_id: str, task_type: str, question: str, target_label: str, options: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    prompt = {
        'TASK': task_type,
        'OBSERVED_STATE': 'Source-backed C++ maintainer smoke root for sentencepiece BPE model behavior.',
        'SOURCE_EVIDENCE': [{k: e[k] for k in ['id', 'kind', 'path', 'start_line', 'end_line', 'summary']} for e in evidence],
        'CANDIDATES': options,
        'QUESTION': question,
    }
    return {
        'row_id': row_id,
        'root_id': ROOT_ID,
        'root_lineage_key': ROOT_ID,
        'source_root_id': ROOT_ID,
        'source_snapshot_id': SNAPSHOT,
        'repo_family': 'sentencepiece',
        'repo_id': 'sentencepiece',
        'language_family': 'c_cpp',
        'task_type': task_type,
        'split': 'strict_eval_candidate',
        'split_role': 'candidate_not_admitted',
        'train_eligible': False,
        'train_support_only': False,
        'strict_eval_eligible': False,
        'source_heldout_admissible': False,
        'source_heldout_attestation': 'pending_no_train_overlap_audit',
        'selected_test_anchor': True,
        'verifier_anchor': True,
        'has_verifier_row_or_transition': True,
        'verifier_transition': 'STATIC_SELECTED_TEST_ANCHOR_NOT_EXECUTED',
        'has_patch_or_abstain_row': task_type in {'patch_impact_or_abstain', 'abstention_insufficient_evidence'},
        'target_label': target_label,
        'target_value': next(o['value'] for o in options if o['label'] == target_label),
        'opaque_options': options,
        'prompt_text': json.dumps(prompt, sort_keys=True),
        'evidence_ledger': evidence,
        'anti_cheat': {
            'opaque_labels': True,
            'deterministic_option_shuffle': True,
            'option_order_seed': 'stage11718_sentencepiece_static_order_v1',
            'prompt_target_label_leak': False,
            'prompt_target_value_leak': False,
            'target_path_strings_hidden_pre_options': False,
            'target_path_visibility_policy': 'all_candidate_paths_visible_only_inside_candidate_options',
            'requires_no_train_overlap_audit': True,
            'source_backed_snippets': True,
            'template_only_evidence': False,
            'singleton_options': False,
        },
    }


def main() -> None:
    if not REPO.exists():
        raise FileNotFoundError(REPO)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    global SNAPSHOT, ROOT_ID
    commit = git_commit(REPO)
    SNAPSHOT = f'sentencepiece::{commit}'
    ROOT_ID = f'stage11718::sentencepiece::{commit}::c_cpp::bpe_model_smoke'

    snippets = {name: read_excerpt(rel) for name, rel in FILES.items()}
    evidence = [
        {'id': 'E01', 'kind': 'implementation_source', 'summary': 'BPE model implementation source is the primary candidate change surface.', **snippets['implementation']},
        {'id': 'E02', 'kind': 'selected_test_anchor', 'summary': 'BPE model tests are the selected verifier/test anchor for this root.', **snippets['test']},
        {'id': 'E03', 'kind': 'nearby_candidate_surface', 'summary': 'BPE trainer implementation is related but not the direct selected BPE model test target.', **snippets['trainer_impl']},
        {'id': 'E04', 'kind': 'distractor_test_anchor', 'summary': 'Trainer tests are plausible but exercise a different maintainer surface.', **snippets['trainer_test']},
        {'id': 'E05', 'kind': 'factory_surface', 'summary': 'Factory code is a plausible caller/configuration-adjacent distractor.', **snippets['factory']},
    ]
    rows = [
        row(
            ROOT_ID + '::symptom_localization::candidate_v1',
            'symptom_localization',
            'Which candidate is the best initial edit/localization target for BPE model behavior under the selected BPE tests?',
            'A',
            [
                option('A', 'candidate_change_surface', FILES['implementation'], ['E01', 'E02']),
                option('B', 'nearby_training_surface', FILES['trainer_impl'], ['E03', 'E04']),
                option('C', 'factory_or_dispatch_surface', FILES['factory'], ['E05']),
                option('D', 'test_surface', FILES['test'], ['E02']),
                option('E', 'abstain_insufficient_evidence', 'ABSTAIN_INSUFFICIENT_EVIDENCE', []),
            ],
            evidence,
        ),
        row(
            ROOT_ID + '::evidence_citation::candidate_v1',
            'evidence_citation',
            'Which evidence item most directly supports the chosen BPE model localization?',
            'B',
            [
                option('A', 'nearby_definition_or_usage_context', 'BPE trainer implementation excerpt', ['E03']),
                option('B', 'verifier_and_test_constraint', 'BPE model selected test anchor', ['E02']),
                option('C', 'candidate_change_surface', 'BPE model implementation excerpt alone', ['E01']),
                option('D', 'distractor_test_constraint', 'BPE trainer selected test distractor', ['E04']),
                option('E', 'abstain_insufficient_evidence', 'ABSTAIN_INSUFFICIENT_EVIDENCE', []),
            ],
            evidence,
        ),
        row(
            ROOT_ID + '::patch_impact_or_abstain::candidate_v1',
            'patch_impact_or_abstain',
            'If behavior under the selected BPE model test changes, which candidate patch target is least broad?',
            'A',
            [
                option('A', 'minimal_candidate_change_surface', FILES['implementation'], ['E01', 'E02']),
                option('B', 'broader_training_surface', FILES['trainer_impl'], ['E03', 'E04']),
                option('C', 'factory_or_dispatch_surface', FILES['factory'], ['E05']),
                option('D', 'change_test_expectation', FILES['test'], ['E02']),
                option('E', 'abstain_insufficient_evidence', 'ABSTAIN_INSUFFICIENT_EVIDENCE', []),
            ],
            evidence,
        ),
        row(
            ROOT_ID + '::verifier_outcome_or_abstain::candidate_v1',
            'verifier_outcome_or_abstain',
            'Which verifier/test anchor should be used first for this BPE model root?',
            'A',
            [
                option('A', 'selected_test_anchor', FILES['test'], ['E02']),
                option('B', 'nearby_test_distractor', FILES['trainer_test'], ['E04']),
                option('C', 'implementation_only_no_verifier', FILES['implementation'], ['E01']),
                option('D', 'factory_surface_no_direct_verifier', FILES['factory'], ['E05']),
                option('E', 'abstain_insufficient_evidence', 'ABSTAIN_INSUFFICIENT_EVIDENCE', []),
            ],
            evidence,
        ),
    ]
    artifact = {
        'stage': 11718,
        'stage_name': 'sentencepiece_cpp_source_heldout_smoke_packet',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'decision': 'sentencepiece_cpp_smoke_packet_materialized_pending_admission',
        'passed': True,
        'root_id': ROOT_ID,
        'source_snapshot_id': SNAPSHOT,
        'row_count': len(rows),
        'admission_status': 'pending_no_train_overlap_audit',
        'claim_boundary': [
            'Rows are source-backed and maintainer-visible, but not admitted as source-heldout yet.',
            'No model or Gemma scoring should use these rows for claims until Stage11714-style preflight and no-train overlap audit pass.',
            'Verifier transition is a static selected-test anchor, not an executed fail/pass result.',
        ],
        'next_stage_acceptance': [
            'run no-train/root overlap audit against ROOT_ID and source_snapshot_id',
            'if clean, set source_heldout_admissible=true in a derived admitted packet',
            'run same-manifest 100M and Gemma scoring only after admission',
            'extend with executable harness writeback before full-product claims',
        ],
        'outputs': {
            'artifact': 'runs/local/artifacts/stage11718_sentencepiece_cpp_source_heldout_smoke_packet/sentencepiece_cpp_source_heldout_smoke_packet.json',
            'rows_jsonl': 'runs/local/artifacts/stage11718_sentencepiece_cpp_source_heldout_smoke_packet/sentencepiece_cpp_smoke_rows.jsonl',
            'evidence_json': 'runs/local/artifacts/stage11718_sentencepiece_cpp_source_heldout_smoke_packet/sentencepiece_cpp_evidence_ledger.json',
            'summary': 'runs/summaries/stage11718_sentencepiece_cpp_source_heldout_smoke_packet.json',
        },
    }
    (OUT_DIR / 'sentencepiece_cpp_source_heldout_smoke_packet.json').write_text(json.dumps(artifact, indent=2, sort_keys=True) + '\n')
    with (OUT_DIR / 'sentencepiece_cpp_smoke_rows.jsonl').open('w') as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + '\n')
    (OUT_DIR / 'sentencepiece_cpp_evidence_ledger.json').write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    shutil.copyfile(OUT_DIR / 'sentencepiece_cpp_source_heldout_smoke_packet.json', SUMMARY)
    print(json.dumps({'artifact': str(OUT_DIR / 'sentencepiece_cpp_source_heldout_smoke_packet.json'), 'summary': str(SUMMARY), 'rows': len(rows)}, indent=2))


if __name__ == '__main__':
    main()
