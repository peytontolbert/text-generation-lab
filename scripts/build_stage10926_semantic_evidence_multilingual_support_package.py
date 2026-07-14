#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10926
NAME = 'stage10926_semantic_evidence_multilingual_support_package'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'semantic_evidence_multilingual_support_package.json'
TRAIN_JSONL = OUT_DIR / 'agentkernel_lite_encdec_train.jsonl'
VALIDATION_JSONL = OUT_DIR / 'agentkernel_lite_encdec_validation.jsonl'
STRICT_JSONL = OUT_DIR / 'agentkernel_lite_encdec_strict_eval.jsonl'
STRESS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_stress_eval.jsonl'
ADDED_ROWS_JSONL = OUT_DIR / 'added_semantic_support_rows.jsonl'

BASE_DIR = ARTIFACTS / 'stage10883_flash_attn_alias_safe_successor_package'
BASE_SUMMARY_JSON = BASE_DIR / 'flash_attn_alias_safe_successor_package.json'
BASE_TRAIN_JSONL = BASE_DIR / 'agentkernel_lite_encdec_train.jsonl'
BASE_VALIDATION_JSONL = BASE_DIR / 'agentkernel_lite_encdec_validation.jsonl'
BASE_STRICT_JSONL = BASE_DIR / 'agentkernel_lite_encdec_strict_eval.jsonl'
BASE_STRESS_JSONL = BASE_DIR / 'agentkernel_lite_encdec_stress_eval.jsonl'

SEMANTIC_DIR = ARTIFACTS / 'stage10925_reviewed_evidence_role_semantic_support_package'
SEMANTIC_SUMMARY_JSON = SEMANTIC_DIR / 'reviewed_evidence_role_semantic_support_package.json'
SEMANTIC_ROWS_JSONL = SEMANTIC_DIR / 'support_rows.jsonl'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def sanitize_train_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated['split'] = 'train'
    updated['train_support_only'] = True
    updated['strict_eval_eligible'] = False
    updated['disable_losses'] = []
    updated['loss_mask'] = {'decoder_ce': True}
    updated['expected_enabled_loss'] = 'decoder_ce'
    return updated


def main() -> None:
    base_summary = load_json(BASE_SUMMARY_JSON)
    semantic_summary = load_json(SEMANTIC_SUMMARY_JSON)
    base_train = [sanitize_train_row(row) for row in load_jsonl(BASE_TRAIN_JSONL)]
    semantic_rows = [sanitize_train_row(row) for row in load_jsonl(SEMANTIC_ROWS_JSONL)]
    validation_rows = load_jsonl(BASE_VALIDATION_JSONL)
    strict_rows = load_jsonl(BASE_STRICT_JSONL)
    stress_rows = load_jsonl(BASE_STRESS_JSONL)

    merged_train = list(base_train) + list(semantic_rows)

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': bool(merged_train) and bool(validation_rows) and bool(strict_rows),
        'decision': 'semantic_evidence_multilingual_support_package_ready',
        'claim_scope': [
            'Add support-only semantic evidence-role supervision on top of the anti-cheat-clean stage10883 multilingual package.',
            'Keep the cleaned 23-row validation and 23-row strict overlays unchanged so any movement can be attributed to train geometry rather than eval drift.',
        ],
        'required_honesty_gates': [
            'All semantic evidence rows remain train_support_only and strict_eval_eligible=false.',
            'Validation and strict rows are copied unchanged from stage10883.',
            'Stress rows remain excluded from promotion claims and unchanged from stage10883.',
            'Known alias-risk tokenizers evidence remains excluded from the semantic support package.',
        ],
        'source_artifacts': {
            'base_summary': rel(BASE_SUMMARY_JSON),
            'base_train': rel(BASE_TRAIN_JSONL),
            'base_validation': rel(BASE_VALIDATION_JSONL),
            'base_strict': rel(BASE_STRICT_JSONL),
            'base_stress': rel(BASE_STRESS_JSONL),
            'semantic_summary': rel(SEMANTIC_SUMMARY_JSON),
            'semantic_rows': rel(SEMANTIC_ROWS_JSONL),
        },
        'metrics': {
            'train_rows_before': len(base_train),
            'semantic_rows_added': len(semantic_rows),
            'train_rows_after': len(merged_train),
            'validation_rows_unchanged': len(validation_rows),
            'strict_rows_unchanged': len(strict_rows),
            'stress_rows_unchanged': len(stress_rows),
            'train_by_language': dict(sorted(Counter(str(row.get('language_family') or 'unknown') for row in merged_train).items())),
            'train_by_task': dict(sorted(Counter(str(row.get('task_type') or 'unknown') for row in merged_train).items())),
            'semantic_targets_added': dict(sorted(Counter(str(row.get('target_text') or 'unknown') for row in semantic_rows).items())),
            'semantic_row_types_added': dict(sorted(Counter('pairwise_contrast' if 'semantic_role_pairwise_contrast' in str(row.get('row_id') or '') else 'semantic_role_full' for row in semantic_rows).items())),
            'base_metrics_snapshot': base_summary.get('metrics'),
            'semantic_metrics_snapshot': {
                'row_count': semantic_summary.get('row_count'),
                'rows_by_language': semantic_summary.get('rows_by_language'),
                'rows_by_target': semantic_summary.get('rows_by_target'),
            },
        },
        'interpretation': [
            'This is the first multilingual support increment that directly targets evidence-role discrimination with semantic targets rather than opaque labels.',
            'It preserves the current bounded canary/eval contract, so a later probe can be judged by unchanged 23-row heldout behavior plus fresh evidence successor slices.',
            'The web lane is present only as train-support stress overlap via code_assist; it does not upgrade pure-web heldout realism claims.',
        ],
        'next_best_step': 'Run a multilingual support probe from the current alias-safe runtime with these added semantic evidence rows, then re-evaluate the unchanged 23-row overlay and the 3-row fresh evidence successor slice.',
        'outputs': {
            'summary_json': rel(SUMMARY_JSON),
            'train_rows_jsonl': rel(TRAIN_JSONL),
            'validation_rows_jsonl': rel(VALIDATION_JSONL),
            'strict_rows_jsonl': rel(STRICT_JSONL),
            'stress_rows_jsonl': rel(STRESS_JSONL),
            'added_rows_jsonl': rel(ADDED_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(ADDED_ROWS_JSONL, semantic_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
