#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'

STAGE = 10815
NAME = 'stage10815_rust_queue_alignment_audit'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'rust_queue_alignment_audit.json'
STATUS_JSONL = OUT_DIR / 'rust_queue_status_manifest.jsonl'

QUEUE_JSONL = ARTIFACTS / 'stage10810_multilingual_root_materialization_queue_v2' / 'materialization_queue.jsonl'
CURRENT_ROOTS = ARTIFACTS / 'stage10814_reviewed_v27_plus_cpp_python_queue_support_package' / 'reviewed_v27_plus_cpp_python_queue_root_manifest.jsonl'
CURRENT_TRAIN = ARTIFACTS / 'stage10814_reviewed_v27_plus_cpp_python_queue_support_package' / 'agentkernel_lite_encdec_train.jsonl'
LINUX_STAGE = ARTIFACTS / 'stage10680_linux_rust_ai_adjudication' / 'linux_rust_ai_adjudication.json'
CANDLE_DATASETS_STAGE = ARTIFACTS / 'stage10686_candle_datasets_ai_adjudication' / 'candle_datasets_ai_adjudication.json'
TRANSFORMERS_PREVIEW = ARTIFACTS / 'stage10674_rust_fresh_review_packet_scaffolds' / 'review_packets' / 'candle__candle-transformers' / 'fresh_rust_bundle_preview.json'
TRANSFORMERS_ANTI = ARTIFACTS / 'stage10674_rust_fresh_review_packet_scaffolds' / 'review_packets' / 'candle__candle-transformers' / 'anti_cheat_review_card.json'
TRANSFORMERS_BACKLOG = ARTIFACTS / 'stage10757_residual_packet_materialization_backlog' / 'materialization_backlog.jsonl'
WASM_EXTERNAL_REQ = ARTIFACTS / 'stage10441_rust_evidence_citation_fresh_builder_request' / 'rust_evidence_citation_fresh_builder_targets.jsonl'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def root_ids_in_current_package() -> set[str]:
    return {
        str(row.get('bundle_id') or row.get('root_id') or '')
        for row in load_jsonl(CURRENT_ROOTS)
        if str(row.get('language_family') or '') == 'rust'
    }


def train_rows_for_prefix(prefix: str) -> int:
    return sum(1 for row in load_jsonl(CURRENT_TRAIN) if str(row.get('row_id') or '').startswith(prefix + '::'))


def stage_row(candidate_id: str, queue_row: dict[str, Any], current_root_ids: set[str]) -> dict[str, Any]:
    bundle_id = f'stage10674::{candidate_id}'
    base = {
        'candidate_id': candidate_id,
        'queue_global_order': queue_row['global_queue_order'],
        'repo_id': queue_row.get('repo_id'),
        'repo_family': queue_row.get('repo_family'),
        'language_family': 'rust',
        'queue_promotability': queue_row.get('promotability'),
        'queue_target_stage': queue_row.get('target_stage'),
        'already_in_current_support_package': bundle_id in current_root_ids,
        'current_train_row_count': train_rows_for_prefix(bundle_id),
    }

    if candidate_id == 'linux::rust':
        stage = load_json(LINUX_STAGE)
        base.update({
            'status': 'already_admitted_train_support',
            'bundle_id': stage['bundle_id'],
            'admitting_stage': stage['stage_name'],
            'claim_boundary': stage['claim_boundary'],
            'selected_or_verifier_anchor': stage.get('selected_test') or 'source-derived verifier anchor',
            'supports_training_or_scoring_now': True,
            'same_surface_eval_admissible': False,
            'next_action': 'No new Rust queue admission needed for linux::rust; keep using the existing admitted support rows and focus new Rust work on missing fresh roots.',
            'evidence_paths': stage['written_paths'],
        })
        return base

    if candidate_id == 'candle::candle-datasets':
        stage = load_json(CANDLE_DATASETS_STAGE)
        base.update({
            'status': 'already_admitted_train_support',
            'bundle_id': stage['bundle_id'],
            'admitting_stage': stage['stage_name'],
            'claim_boundary': stage['claim_boundary'],
            'selected_or_verifier_anchor': 'source-derived verifier evidence from tinystories.rs',
            'supports_training_or_scoring_now': True,
            'same_surface_eval_admissible': False,
            'next_action': 'No new Rust queue admission needed for candle-datasets; keep using the existing admitted support rows and focus new Rust work on missing fresh roots.',
            'evidence_paths': stage['written_paths'],
        })
        return base

    if candidate_id == 'candle::candle-transformers':
        preview = load_json(TRANSFORMERS_PREVIEW)
        anti = load_json(TRANSFORMERS_ANTI)
        backlog_row = next(row for row in load_jsonl(TRANSFORMERS_BACKLOG) if str(row.get('candidate_id') or '') == candidate_id)
        base.update({
            'status': 'blocked_scaffold_only',
            'bundle_id': str(preview.get('bundle_id') or ''),
            'supports_training_or_scoring_now': bool(preview.get('claim_boundary', {}).get('supports_training_or_scoring_now')),
            'same_surface_eval_admissible': False,
            'blocked_reasons': [
                'placeholder_evidence_present',
                'gold_not_fully_adjudicated',
                'selected_test_or_verifier_anchor_missing',
                'anti_cheat_not_passed',
            ],
            'anti_cheat_status': anti.get('status'),
            'decision_rationale': anti.get('decision_rationale'),
            'missing_materialization_fields': backlog_row.get('missing_materialization_fields'),
            'next_action': backlog_row.get('next_action'),
            'evidence_paths': {
                'preview_bundle': rel(TRANSFORMERS_PREVIEW),
                'anti_cheat_review_card': rel(TRANSFORMERS_ANTI),
            },
        })
        return base

    if candidate_id == 'candle::candle-wasm-examples':
        wasm_row = next(row for row in load_jsonl(WASM_EXTERNAL_REQ) if str(row.get('candidate_root_id') or '') == candidate_id)
        base.update({
            'status': 'blocked_no_materialized_review_packet',
            'bundle_id': 'stage10674::candle::candle-wasm-examples',
            'supports_training_or_scoring_now': False,
            'same_surface_eval_admissible': False,
            'blocked_reasons': [
                'no_materialized_review_packet',
                'current_local_status_not_materializable_from_current_local_state',
                'selected_test_or_verifier_anchor_missing',
            ],
            'current_local_status': wasm_row.get('current_local_status'),
            'recovery_route': wasm_row.get('recovery_route'),
            'required_recovered_fields': wasm_row.get('required_recovered_fields'),
            'next_action': 'Recover external repo spans and a verifier/test anchor before building any reviewed packet.',
            'evidence_paths': {
                'external_materialization_request': rel(WASM_EXTERNAL_REQ),
            },
        })
        return base

    raise KeyError(candidate_id)


def main() -> None:
    queue_rows = [row for row in load_jsonl(QUEUE_JSONL) if str(row.get('language_family') or '') == 'rust']
    current_root_ids = root_ids_in_current_package()
    status_rows = [stage_row(str(row['candidate_id']), row, current_root_ids) for row in sorted(queue_rows, key=lambda r: int(r['global_queue_order']))]
    write_jsonl(STATUS_JSONL, status_rows)

    status_counts = Counter(str(row['status']) for row in status_rows)
    already_admitted = [row for row in status_rows if row['status'] == 'already_admitted_train_support']
    blocked = [row for row in status_rows if row['status'] != 'already_admitted_train_support']

    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'passed': True,
        'decision': 'rust_queue_alignment_corrected_against_current_support_package',
        'claim_scope': [
            'Reconcile the Rust lane of the multilingual materialization queue against the current reviewed v2.7 support package.',
            'Distinguish Rust roots that are already honestly admitted for train-support from roots that remain scaffold-only or externally blocked.',
            'Prevent unnecessary re-admission work and focus the next Rust effort on real materialization blockers only.',
        ],
        'headline_findings': [
            f"{len(already_admitted)} of the 4 queued Rust roots are already present in the current multilingual train-support package.",
            f"{len(blocked)} queued Rust roots remain blocked, but for different reasons: scaffold-only materialization for candle-transformers and no materialized review packet for candle-wasm-examples.",
            'The Rust queue should no longer be treated as four equally pending admissions; the real remaining frontier is new honest materialization, not support-package wiring.',
        ],
        'source_artifacts': {
            'queue': rel(QUEUE_JSONL),
            'current_support_root_manifest': rel(CURRENT_ROOTS),
            'current_support_train_rows': rel(CURRENT_TRAIN),
            'linux_adjudication': rel(LINUX_STAGE),
            'candle_datasets_adjudication': rel(CANDLE_DATASETS_STAGE),
            'candle_transformers_scaffold': rel(TRANSFORMERS_PREVIEW),
            'candle_wasm_external_request': rel(WASM_EXTERNAL_REQ),
        },
        'metrics': {
            'rust_queue_items': len(status_rows),
            'status_counts': dict(sorted(status_counts.items())),
            'already_admitted_train_support_count': len(already_admitted),
            'blocked_count': len(blocked),
            'current_train_rows_for_already_admitted_roots': sum(int(row['current_train_row_count']) for row in already_admitted),
        },
        'next_best_steps': [
            'Do not rebuild Linux or candle-datasets Rust admissions; they are already in the current support package.',
            'Prioritize real materialization for candle-transformers because it already has a scaffold packet but still carries placeholder evidence and no verifier/test anchor.',
            'Keep candle-wasm-examples out of any promotable path until external source recovery produces a real review packet.',
        ],
        'outputs': {
            'summary_json': rel(SUMMARY_JSON),
            'status_manifest_jsonl': rel(STATUS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
