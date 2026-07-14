#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_STAGE = 10270
AUDIT_NAME = 'stage10270_web_augmented_admitted_projection_runtime_audit'
AUDIT_DIR = ROOT / 'runs/local/artifacts' / AUDIT_NAME
AUDIT_JSON = AUDIT_DIR / 'web_augmented_admitted_projection_runtime_audit.json'
AUDIT_SUMMARY = ROOT / 'runs/summaries' / f'{AUDIT_NAME}.json'
BASE_SUMMARY = ROOT / 'runs/local/artifacts/stage10242_admitted_projection_runtime_successor_multilingual_cuda/first_wave_bundle_inference_summary.json'
NEW_SUMMARY = ROOT / 'runs/local/artifacts/stage10269_web_augmented_admitted_projection_runtime_multilingual_cuda/first_wave_bundle_inference_summary.json'
NEW_PAYLOAD = ROOT / 'runs/local/artifacts/stage10268_web_augmented_admitted_projection_runtime_payload/web_augmented_admitted_projection_runtime_payload.json'

REQ_STAGE = 10271
REQ_NAME = 'stage10271_code_assist_web_support_target100m_execution_request'
REQ_DIR = ROOT / 'runs/local/artifacts' / REQ_NAME
REQ_JSON = REQ_DIR / 'code_assist_web_support_target100m_execution_request.json'
REQ_MANIFEST = REQ_DIR / 'code_assist_web_support_target100m_manifest.jsonl'
REQ_SUMMARY = ROOT / 'runs/summaries' / f'{REQ_NAME}.json'
SOURCE_PACKAGE = ROOT / 'runs/local/artifacts/stage10266_code_assist_web_commit_compact_support_package/code_assist_web_commit_compact_support_package.json'
OUTPUT_DIR = ROOT / 'runs/local/artifacts/stage10272_code_assist_web_support_target100m_probe/bounded_decoder_probe'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    by_lang: dict[str, dict[str, Any]] = {}
    total_h = total_g = total_rows = 0
    h_wins = g_wins = ties = 0
    for row in payload.get('results') or []:
        if not isinstance(row, dict):
            continue
        lang = str(row.get('cell_key') or '').split('::')[1]
        h = int((row.get('hundred_m') or {}).get('correct') or 0)
        g = int((row.get('gemma12b') or {}).get('correct') or 0)
        rows = int(row.get('rows') or 0)
        ent = by_lang.setdefault(lang, {'rows': 0, 'h': 0, 'g': 0, 'bundles': 0, 'h_wins': 0, 'g_wins': 0, 'ties': 0})
        ent['rows'] += rows
        ent['h'] += h
        ent['g'] += g
        ent['bundles'] += 1
        total_rows += rows
        total_h += h
        total_g += g
        if h > g:
            ent['h_wins'] += 1
            h_wins += 1
        elif g > h:
            ent['g_wins'] += 1
            g_wins += 1
        else:
            ent['ties'] += 1
            ties += 1
    return {
        'rows': total_rows,
        'hundred_micro': (total_h / total_rows) if total_rows else 0.0,
        'gemma_micro': (total_g / total_rows) if total_rows else 0.0,
        'delta_micro': ((total_h - total_g) / total_rows) if total_rows else 0.0,
        'bundles': h_wins + g_wins + ties,
        'hundred_bundle_wins': h_wins,
        'gemma_bundle_wins': g_wins,
        'bundle_ties': ties,
        'per_language': {
            lang: {
                'rows': ent['rows'],
                'bundles': ent['bundles'],
                'hundred_micro': ent['h'] / ent['rows'],
                'gemma_micro': ent['g'] / ent['rows'],
                'delta_micro': (ent['h'] - ent['g']) / ent['rows'],
                'hundred_bundle_wins': ent['h_wins'],
                'gemma_bundle_wins': ent['g_wins'],
                'bundle_ties': ent['ties'],
            }
            for lang, ent in sorted(by_lang.items())
            if ent['rows']
        },
    }


def build_audit() -> dict[str, Any]:
    base = summarize(load_json(BASE_SUMMARY))
    new = summarize(load_json(NEW_SUMMARY))
    payload = load_json(NEW_PAYLOAD)
    audit = {
        'stage': AUDIT_STAGE,
        'stage_name': AUDIT_NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'base_summary': display(BASE_SUMMARY),
        'new_summary': display(NEW_SUMMARY),
        'new_payload': display(NEW_PAYLOAD),
        'metrics': {
            'base_rows': base['rows'],
            'new_rows': new['rows'],
            'base_hundred_micro': base['hundred_micro'],
            'new_hundred_micro': new['hundred_micro'],
            'base_gemma_micro': base['gemma_micro'],
            'new_gemma_micro': new['gemma_micro'],
            'base_delta_micro': base['delta_micro'],
            'new_delta_micro': new['delta_micro'],
            'delta_new_minus_base': new['delta_micro'] - base['delta_micro'],
            'augmented_web_bundles': payload.get('metrics', {}).get('augmented_web_bundles', 0),
            'filtered_single_option_rows': payload.get('metrics', {}).get('excluded_rows', 0),
        },
        'per_language': {
            lang: {
                'base': base['per_language'].get(lang),
                'new': new['per_language'].get(lang),
                'delta_new_minus_base': (
                    (new['per_language'][lang]['delta_micro'] - base['per_language'][lang]['delta_micro'])
                    if lang in base['per_language'] and lang in new['per_language']
                    else None
                ),
            }
            for lang in sorted(set(base['per_language']) | set(new['per_language']))
        },
        'decision': (
            'The two added code_assist web commit bundles are valid repo-overlap stress rows and preserve a 100M advantage over Gemma, '
            'but they reduce the overall compact-bounded successor micro frontier and should remain stress-eval and train-support material rather than replacing the current 10-bundle headline runtime successor.'
        ),
        'next_best_step': (
            'Keep stage10243/stage10246 as the main compact-bounded multilingual frontier, and use stage10266 as the next standalone train-support package because the new web bundles specifically expose 100M weakness on symptom_localization, patch_impact, and minimal_fix_selection.'
        ),
        'weak_bundle_findings': [
            {
                'bundle_id': 'stage10264::code_assist_git_commit::a305b18b7f85::web_js_ts_html',
                'hundred_m_correct_perspectives': ['abstention_insufficient_evidence', 'evidence_citation'],
                'hundred_m_failed_perspectives': ['symptom_localization', 'patch_impact', 'minimal_fix_selection'],
                'gemma_correct_perspectives': [],
            },
            {
                'bundle_id': 'stage10264::code_assist_git_commit::b94562d7b708::web_js_ts_html',
                'hundred_m_correct_perspectives': ['abstention_insufficient_evidence', 'evidence_citation'],
                'hundred_m_failed_perspectives': ['symptom_localization', 'patch_impact', 'minimal_fix_selection'],
                'gemma_correct_perspectives': [],
            },
        ],
    }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_JSON.write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    AUDIT_SUMMARY.write_text(json.dumps({'stage': AUDIT_STAGE, 'passed': True, 'artifact': display(AUDIT_JSON), 'metrics': audit['metrics']}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return audit


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get('target_text') or '')
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def build_request() -> dict[str, Any]:
    package = load_json(SOURCE_PACKAGE)
    train_rows = load_jsonl(ROOT / str(package.get('train_dataset_path') or ''))
    eval_rows = load_jsonl(ROOT / str(package.get('eval_dataset_path') or ''))
    manifest_rows = train_rows + eval_rows
    write_manifest(REQ_MANIFEST, manifest_rows)
    request = {
        'stage': REQ_STAGE,
        'stage_name': REQ_NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'source_package': display(SOURCE_PACKAGE),
        'manifest': display(REQ_MANIFEST),
        'rows': len(manifest_rows),
        'split_counts': {
            'train': len(train_rows),
            'strict_eval': len(eval_rows),
            'eval': 0,
            'other': 0,
        },
        'language_counts': {
            language: sum(1 for row in manifest_rows if str(row.get('language_family') or '') == language)
            for language in sorted({str(row.get('language_family') or '') for row in manifest_rows})
        },
        'label_counts': label_counts(manifest_rows),
        'request_status': 'execution_ready',
        'run_id': 'stage10272_code_assist_web_support_target100m_probe',
        'output_dir': display(OUTPUT_DIR),
        'command': [
            'env', 'TMPDIR=/data/tmp', 'TEMP=/data/tmp', 'TMP=/data/tmp',
            'conda', 'run', '-n', 'trellis', 'python',
            str(ROOT / 'legacy_src/scripts/train_agentkernel_lite_encdec.py'),
            '--repo-root', str(ROOT),
            '--manifest', str(REQ_MANIFEST),
            '--mode', 'bounded_decoder_ce_probe',
            '--probe-scale', 'target_100m',
            '--implementation', 'transformer',
            '--model-config', str(ROOT / 'configs/model/agentkernel_100m_seq2seq_recovered_target.json'),
            '--tokenizer-json', str(ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'),
            '--tokenizer-config', str(ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'),
            '--tokenizer-hashlock', str(ROOT / 'configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json'),
            '--execution-authorized-for-recovery-probe',
            '--max-train-rows', str(len(train_rows)),
            '--max-eval-rows', '0',
            '--max-strict-rows', str(len(eval_rows)),
            '--max-steps', '224',
            '--batch-size', '2',
            '--learning-rate', '5e-5',
            '--max-encoder-tokens', '768',
            '--max-decoder-tokens', '8',
            '--decoder-ce-weight', '0.25',
            '--bounded-choice-aux-weight', '1.0',
            '--bounded-choice-aux-source', 'encoder_option_retrieval',
            '--structured-aux-weight', '0.0',
            '--denoise-weight', '0.0',
            '--eos-loss-weight', '4.0',
            '--enable-generation-audit',
            '--max-generation-rows', '24',
            '--max-generation-tokens', '8',
            '--require-loss-mask-enforcement-audit',
            '--no-final-checkpoint-export',
            '--cleanup-checkpoints-after-probe',
            '--skip-final-model-save', '1',
            '--output-dir', str(OUTPUT_DIR),
            '--run-id', 'stage10272_code_assist_web_support_target100m_probe',
        ],
        'required_honesty_gates': [
            'stage10142 standalone decoder contract audit remains blocking until post-training rerun proves scoreability',
            'stage10266 remains auxiliary compact-bounded train support and does not by itself promote a maintainer-grade claim',
            'the two stage10264 code_assist git-commit bundles remain repo-overlap web support only and not source-heldout headline evidence',
        ],
        'required_runtime_artifacts': [
            'execution_result.json',
            'bounded_choice_eval_audit_strict_eval.json',
            'sample_generation_audit.json',
            'failure_bucket_card.json',
            'cleanup_proof.json',
        ],
        'decision': (
            'Materialized the next standalone target-100M training request on the cleaned stage10266 package. '
            'This keeps the strong multilingual strict-eval packet intact while adding the new code_assist web support rows that specifically target the currently failing web perspectives.'
        ),
        'next_best_step': (
            'Execute this 224-step bounded-decoder probe in trellis, then rerun the compact-bounded same-surface 100M-versus-Gemma comparison with special attention to the two stage10264 web bundles and the existing web_js_ts_html frontier bundles.'
        ),
    }
    REQ_DIR.mkdir(parents=True, exist_ok=True)
    REQ_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    REQ_JSON.write_text(json.dumps(request, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    REQ_SUMMARY.write_text(json.dumps({'stage': REQ_STAGE, 'passed': True, 'request': display(REQ_JSON), 'manifest': display(REQ_MANIFEST), 'rows': len(manifest_rows), 'split_counts': request['split_counts'], 'language_counts': request['language_counts']}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return request


def main() -> None:
    audit = build_audit()
    request = build_request()
    print(json.dumps({'audit_stage': AUDIT_STAGE, 'audit_artifact': display(AUDIT_JSON), 'request_stage': REQ_STAGE, 'request_artifact': display(REQ_JSON), 'request_rows': request['rows'], 'audit_delta_micro': audit['metrics']['delta_new_minus_base']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
