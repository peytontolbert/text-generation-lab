#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10566
NAME = "stage10566_visible_candidate_decisive_evidence_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "visible_candidate_decisive_evidence_probe_request.json"
COMMAND_JSON = OUT_DIR / "visible_candidate_decisive_evidence_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "visible_candidate_decisive_evidence_probe_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SUPPORT_PACKAGE = ROOT / "runs/local/artifacts/stage10565_visible_candidate_decisive_evidence_support_package/visible_candidate_decisive_evidence_support_package.json"
SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10565_visible_candidate_decisive_evidence_support_package/visible_candidate_decisive_evidence_support_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/strict_eval_rows.jsonl"
EVAL_ROWS = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/eval_rows.jsonl"
CANARY_AUDIT = ROOT / "runs/local/artifacts/stage10558_masked_projection_successor_with_v27_preservation_canary_audit/masked_projection_successor_with_v27_preservation_canary_audit.json"
TRANSITION_AUDIT = ROOT / "runs/local/artifacts/stage10563_visible_candidate_transition_bounded_audit/visible_candidate_transition_bounded_audit.json"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10556_masked_projection_successor_with_v27_preservation_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_REF = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path('/data/tmp')

RUN_ID = "stage10567_visible_candidate_decisive_evidence_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10567_visible_candidate_decisive_evidence_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10567_visible_candidate_decisive_evidence_probe/runtime_model"


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def normalize_rows() -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    split_counts = {'train': 0, 'eval': 0, 'strict_eval': 0}
    language_counts: dict[str, int] = {}
    for path, out_split in ((SUPPORT_ROWS, 'train'), (EVAL_ROWS, 'eval'), (STRICT_ROWS, 'strict_eval')):
        for row in load_jsonl(path):
            copied = json.loads(json.dumps(row))
            copied['split'] = out_split
            copied['loss_mask'] = {'decoder_ce': True}
            copied['expected_enabled_loss'] = 'decoder_ce'
            copied['disable_losses'] = [] if out_split == 'train' else ['denoise_ce', 'runtime_reward', 'structured_aux']
            rows.append(copied)
            split_counts[out_split] += 1
            language = str(copied.get('language_family') or 'unknown')
            language_counts[language] = language_counts.get(language, 0) + 1
    return rows, split_counts, dict(sorted(language_counts.items()))


def build_command(split_counts: dict[str, int]) -> list[str]:
    return [
        'env',
        f'TMPDIR={TMPDIR}',
        f'TEMP={TMPDIR}',
        f'TMP={TMPDIR}',
        'AGENTKERNEL_TRAIN_DEVICE=cuda',
        'conda', 'run', '-n', 'trellis',
        'python', str(TRAINER),
        '--repo-root', str(ROOT),
        '--manifest', str(MANIFEST_JSONL),
        '--mode', 'bounded_decoder_ce_probe',
        '--probe-scale', 'target_100m',
        '--implementation', 'transformer',
        '--model-config', str(MODEL_CONFIG),
        '--tokenizer-json', str(TOKENIZER_JSON),
        '--tokenizer-config', str(TOKENIZER_CONFIG),
        '--tokenizer-hashlock', str(TOKENIZER_HASHLOCK),
        '--execution-authorized-for-recovery-probe',
        '--max-train-rows', str(split_counts['train']),
        '--max-eval-rows', str(split_counts['eval']),
        '--max-strict-rows', str(split_counts['strict_eval']),
        '--max-steps', '96',
        '--batch-size', '1',
        '--learning-rate', '8e-6',
        '--max-encoder-tokens', '1024',
        '--max-decoder-tokens', '8',
        '--decoder-ce-weight', '1.0',
        '--bounded-choice-aux-weight', '1.0',
        '--bounded-choice-aux-source', 'decoder_first_step',
        '--structured-aux-weight', '0.0',
        '--denoise-weight', '0.0',
        '--eos-loss-weight', '2.0',
        '--enable-generation-audit',
        '--max-generation-rows', '24',
        '--max-generation-tokens', '8',
        '--require-loss-mask-enforcement-audit',
        '--allow-runtime-model-save-for-harness',
        '--runtime-model-save-dir', str(ROOT / RUNTIME_MODEL_DIR),
        '--initialize-from-runtime-model', str(INIT_RUNTIME),
        '--preservation-reference-runtime-model', str(PRESERVATION_REF),
        '--preservation-kl-weight', '1.0',
        '--no-final-checkpoint-export',
        '--skip-final-model-save', '1',
        '--output-dir', str(ROOT / OUTPUT_DIR),
        '--run-id', RUN_ID,
    ]


def main() -> None:
    support_package = load_json(SUPPORT_PACKAGE)
    canary = load_json(CANARY_AUDIT)
    transition = load_json(TRANSITION_AUDIT)
    manifest_rows, split_counts, language_counts = normalize_rows()
    command = build_command(split_counts)
    request = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': bool(support_package.get('passed')),
        'decision': 'visible_candidate_decisive_evidence_probe_ready',
        'source_support_package': display(SUPPORT_PACKAGE),
        'manifest': display(MANIFEST_JSONL),
        'run_id': RUN_ID,
        'output_dir': OUTPUT_DIR,
        'runtime_model_dir': RUNTIME_MODEL_DIR,
        'rows': len(manifest_rows),
        'split_counts': split_counts,
        'language_counts': language_counts,
        'initialize_from_runtime_model': display(INIT_RUNTIME),
        'preservation_reference_runtime_model': display(PRESERVATION_REF),
        'claim_scope': [
            'Diagnostic multilingual target-100M probe that trains only on stage10565 decisive-evidence support while keeping stage10561 rebuilt strict rows held out.',
            'Tests whether decoder_first_step-visible-candidate support can raise decisive_evidence_top1 on the rebuilt 54-row strict successor slice without regressing the repaired v2.7 canary.',
            'Not promotable unless post-run strict and canary audits both improve or hold under the declared gates.',
        ],
        'motivation': {
            'stage10563_decoder_first_step_overall_accuracy': (((transition.get('summary') or {}).get('decoder_first_step')) or {}).get('accuracy'),
            'stage10563_decisive_evidence_decoder_accuracy': ((((transition.get('per_target_subtype') or {}).get('decisive_evidence_top1')) or {}).get('decoder_first_step') or {}).get('accuracy'),
            'stage10558_canary_bounded_accuracy': ((canary.get('summary') or {}).get('bounded_accuracy')),
        },
        'training_deltas': {
            'train_support_manifest': 'stage10565_visible_candidate_decisive_evidence_support_package',
            'bounded_choice_aux_source': {'from': 'mixed_or_default', 'to': 'decoder_first_step'},
            'max_steps': '96',
            'learning_rate': '8e-6',
            'max_decoder_tokens': '8',
        },
        'required_honesty_gates': [
            'stage10561 strict_eval rows remain eval-only and never enter train support',
            'stage10565 rows remain train-only and root-disjoint from stage10561 strict roots',
            'stage10558 repaired v2.7 canary must be rerun post-probe and must not regress below 22/24 bounded accuracy without being treated as a failed promotion candidate',
            'stage10563 visible-candidate transition audit must be rerun post-probe so decisive_evidence_top1 is measured under decoder_first_step scoring, not only greedy generation',
            'retrieve_answer_abstain remains non-headline until a non-constant negative set exists',
            'same-manifest Gemma comparison on stage10561 strict rows must be reported separately from bounded-choice saved-runtime audits',
        ],
        'post_run_required_artifacts': [
            'bounded_decoder_probe/execution_result.json',
            'post-run stage10558-style canary audit against repaired v2.7 overlay',
            'post-run stage10563-style bounded transition audit against stage10561 strict rows',
            'same-manifest comparison versus Gemma on stage10561 strict rows',
        ],
        'known_limits': [
            'Rust decisive-evidence support is only 2 base roots and web only 3 base roots in stage10565, so any multilingual uplift must still be read conservatively.',
            'This probe targets decisive evidence only; it is not a full rebuilt-successor curriculum.',
        ],
        'next_best_step': 'Launch the stage10567 probe from this request, then rerun the canary, stage10563 bounded-transition audit, and same-manifest Gemma comparison before deciding whether the support package materially moved the frontier.',
        'command': command,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST_JSONL, manifest_rows)
    write_json(COMMAND_JSON, {'command': command, 'cwd': str(ROOT), 'env': 'trellis', 'tmpdir': str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, {
        'stage': STAGE,
        'passed': True,
        'request': display(REQUEST_JSON),
        'manifest': display(MANIFEST_JSONL),
        'split_counts': split_counts,
        'language_counts': language_counts,
    })
    print(json.dumps({'stage': STAGE, 'passed': request['passed'], 'run_id': RUN_ID, 'rows': len(manifest_rows)}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
