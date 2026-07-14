#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10610
NAME = "stage10610_repaired_v27_fresh_root_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "repaired_v27_fresh_root_probe_request.json"
COMMAND_JSON = OUT_DIR / "repaired_v27_fresh_root_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "repaired_v27_fresh_root_probe_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SUPPORT_PACKAGE = ROOT / "runs/local/artifacts/stage10477_post_plateau_fresh_root_support_package/post_plateau_fresh_root_support_package.json"
SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10477_post_plateau_fresh_root_support_package/post_plateau_fresh_root_support_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"
PROMOTION_CONTRACT = ROOT / "runs/local/artifacts/stage10609_reviewed_v27_multilingual_promotion_contract/reviewed_v27_multilingual_promotion_contract.json"
LEAK_AUDIT = ROOT / "runs/local/artifacts/stage10437_repaired_v27_strict_overlay_eval_hacking_audit/repaired_v27_strict_overlay_eval_hacking_audit.json"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10490_deleaked_python_promotable_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_REF = ROOT / "runs/local/artifacts/stage10490_deleaked_python_promotable_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path('/data/tmp')

RUN_ID = "stage10611_repaired_v27_fresh_root_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10611_repaired_v27_fresh_root_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10611_repaired_v27_fresh_root_probe/runtime_model"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    if not path.exists():
        return rows
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line=line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def normalize_rows() -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    rows=[]
    split_counts={'train':0,'eval':0,'strict_eval':0}
    language_counts={}
    for path, out_split in ((SUPPORT_ROWS, 'train'), (STRICT_ROWS, 'strict_eval')):
        for row in load_jsonl(path):
            copied=json.loads(json.dumps(row))
            copied['split']=out_split
            copied['loss_mask']={'decoder_ce': True}
            copied['expected_enabled_loss']='decoder_ce'
            copied['disable_losses']=[] if out_split == 'train' else ['denoise_ce','runtime_reward','structured_aux']
            rows.append(copied)
            split_counts[out_split]+=1
            language=str(copied.get('language_family') or 'unknown')
            language_counts[language]=language_counts.get(language, 0)+1
    return rows, split_counts, dict(sorted(language_counts.items()))


def build_command(split_counts: dict[str, int]) -> list[str]:
    return [
        'env',
        f'TMPDIR={TMPDIR}',
        f'TEMP={TMPDIR}',
        f'TMP={TMPDIR}',
        'AGENTKERNEL_TRAIN_DEVICE=cuda',
        'conda','run','-n','trellis',
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
        '--max-eval-rows', '0',
        '--max-strict-rows', str(split_counts['strict_eval']),
        '--max-steps', '48',
        '--batch-size', '1',
        '--learning-rate', '6e-6',
        '--max-encoder-tokens', '768',
        '--max-decoder-tokens', '8',
        '--decoder-ce-weight', '0.2',
        '--bounded-choice-aux-weight', '1.0',
        '--bounded-choice-aux-source', 'encoder_option_retrieval',
        '--structured-aux-weight', '0.0',
        '--denoise-weight', '0.0',
        '--eos-loss-weight', '4.0',
        '--enable-generation-audit',
        '--max-generation-rows', '12',
        '--max-generation-tokens', '8',
        '--require-loss-mask-enforcement-audit',
        '--allow-runtime-model-save-for-harness',
        '--runtime-model-save-dir', str(ROOT / RUNTIME_MODEL_DIR),
        '--initialize-from-runtime-model', str(INIT_RUNTIME),
        '--preservation-reference-runtime-model', str(PRESERVATION_REF),
        '--preservation-kl-weight', '2.0',
        '--no-final-checkpoint-export',
        '--skip-final-model-save', '1',
        '--output-dir', str(ROOT / OUTPUT_DIR),
        '--run-id', RUN_ID,
    ]


def main() -> None:
    support_package = load_json(SUPPORT_PACKAGE)
    promotion_contract = load_json(PROMOTION_CONTRACT)
    leak_audit = load_json(LEAK_AUDIT)
    gate = load_json(PROMOTION_GATE)
    manifest_rows, split_counts, language_counts = normalize_rows()
    command = build_command(split_counts)
    request = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': bool(support_package.get('passed')),
        'decision': 'repaired_v27_fresh_root_probe_ready',
        'source_support_package': display(SUPPORT_PACKAGE),
        'promotion_contract': display(PROMOTION_CONTRACT),
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
            'Fresh-root standalone probe against the repaired v2.7 strict overlay using executable post-plateau Python and Rust support rows.',
            'Python movement is the main promotable signal because those support roots are executable and disjoint; Rust movement remains diagnostic until non-tokenizers reviewed roots exist.',
            'This run stays on the stable constrained-choice standalone path defined by the current reviewed-v2.7 promotion contract.',
        ],
        'motivation': {
            'support_row_count': ((support_package.get('metrics') or {}).get('support_row_count')),
            'strict_rows': split_counts['strict_eval'],
            'overlay_rows_with_prompt_target_leak': ((leak_audit.get('summary') or {}).get('rows_with_prompt_target_leak')),
            'current_promotion_accuracy': (((gate.get('current_candidate_summary') or {}).get('baseline_accuracy'))),
            'primary_metric': (((promotion_contract.get('promotion_surface') or {}).get('primary_metric'))),
        },
        'training_deltas': {
            'train_support_manifest': 'stage10477_post_plateau_fresh_root_support_package',
            'initialize_from_runtime_model': 'stage10490_deleaked_python_promotable_probe',
            'preservation_reference_runtime_model': 'stage10490_deleaked_python_promotable_probe',
            'max_steps': '48',
            'learning_rate': '6e-6',
            'bounded_choice_aux_source': 'encoder_option_retrieval',
            'decoder_ce_weight': '0.2',
        },
        'required_honesty_gates': [
            'strict path must remain the repaired v2.7 overlay with zero prompt-target leak rows',
            'no same-root replay from the current strict overlay into train support',
            'no tokenizers strict-row copy into train support',
            'candle-core rust rows remain diagnostic-only and cannot justify a Rust promotion claim by themselves',
            'headline metric remains constrained_choice_top1_accuracy on the standalone compact bounded surface',
        ],
        'post_run_required_artifacts': [
            'bounded_decoder_probe/execution_result.json',
            'post-run repaired overlay eval-hacking audit against stage10611 runtime',
            'post-run repaired overlay margin/residual audit against stage10611 runtime',
            'promotion gate check versus the 22/24 standalone baseline',
        ],
        'known_limits': [
            'The current support package only covers Python and Rust; C/C++ and Web rely on preservation rather than fresh support in this run.',
            'Any Rust movement remains diagnostic until a non-tokenizers reviewed residual-root artifact exists.',
        ],
        'next_best_step': 'Launch the stage10611 probe from this request, then judge it only through the repaired-overlay promotion gate and fresh-root honesty constraints.',
        'command': command,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST_JSONL, manifest_rows)
    write_json(COMMAND_JSON, {'command': command, 'cwd': str(ROOT), 'env': 'trellis', 'tmpdir': str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, {'stage': STAGE, 'passed': True, 'request': display(REQUEST_JSON), 'manifest': display(MANIFEST_JSONL), 'split_counts': split_counts, 'language_counts': language_counts})
    print(json.dumps({'stage': STAGE, 'passed': request['passed'], 'run_id': RUN_ID, 'rows': len(manifest_rows)}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
