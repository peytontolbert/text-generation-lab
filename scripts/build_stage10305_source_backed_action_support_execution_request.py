#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10305
NAME = "stage10305_source_backed_action_support_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
INVENTORY_JSON = OUT_DIR / "source_backed_action_support_inventory.json"
TRAIN_ROWS_JSONL = OUT_DIR / "source_backed_action_support_train_rows.jsonl"
MANIFEST_JSONL = OUT_DIR / "source_backed_action_support_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "source_backed_action_support_execution_request.json"
COMMAND_JSON = OUT_DIR / "source_backed_action_support_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10302_hf_local_support_execution_request/hf_local_support_manifest.jsonl"
SOURCE_PACKET = ROOT / "runs/local/artifacts/stage10110_real_session_shortcut_safe_successor_packet/real_session_shortcut_safe_successor_packet.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10303_hf_local_support_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path('/data/tmp')

RUN_ID = "stage10306_source_backed_action_support_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10306_source_backed_action_support_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10306_source_backed_action_support_probe/runtime_model"
MAX_STEPS = 48
LEARNING_RATE = "8e-6"

SELECTED = [
    {
        "row_id": "stage10110::localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_24t23_41_47_019ab83e_b023_7553_a34c_b93e_src_main_js_index_html_440e122a0f_aug_1500000_8b46e7f662::web_entrypoint_vs_implementation",
        "gold_candidate_id": "B",
        "support_family": "web_entrypoint_real_session",
        "ai_review": {
            "expert_passed": True,
            "anti_cheat_passed": True,
            "selected_candidate_rationale": "The prompt-visible evidence directly shows an edit flow centered on `index.html`, including `cat index.html`, an `apply_patch` add-file action for the same surface, and an HTML entry-shell snippet. The competing JavaScript implementation snippet is plausible but less directly tied to the visible maintenance operation.",
            "anti_cheat_rationale": "This row still has singleton web-slice risk, but candidate order can be neutralized through permutation. The answer is supported by prompt-visible maintenance evidence rather than hidden changed-path metadata, and it is useful as train-only auxiliary support rather than as a benchmark claim.",
        },
    },
    {
        "row_id": "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_19t21_03_20_019d07e8_f3b4_7ae3_8bdc_1638_agent_kernel_loop_py_agent_kernel_policy_py_evals_harness_py_tests_test_eval_py__028cf3a98b_aug_1500000_8b46e7f662::python_implementation_vs_implementation",
        "gold_candidate_id": "B",
        "support_family": "python_loop_vs_policy_real_session",
        "ai_review": {
            "expert_passed": True,
            "anti_cheat_passed": True,
            "selected_candidate_rationale": "The visible evidence and selected tests lean toward loop execution behavior rather than AST/policy utilities: the packet includes `test_loop`, `test_liftoff_loop`, runtime diagnostics, and a loop-oriented implementation preview, so the loop surface is the most plausible first implementation to inspect.",
            "anti_cheat_rationale": "Both candidates are implementations and both are plausible, which is the right geometry for action-taking support. The row is not admitted as a claim cell; it is being used train-only with label permutation to reduce position priors.",
        },
    },
    {
        "row_id": "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_45_019d39fb_a380_7a30_8790_9d59_agent_kernel_improvement_py_agent_kernel_modeling_adapter_training_py_agent_kern_94b87c02df_aug_1500000_8b46e7f662::python_implementation_vs_implementation",
        "gold_candidate_id": "A",
        "support_family": "python_improvement_vs_adapter_training_real_session",
        "ai_review": {
            "expert_passed": True,
            "anti_cheat_passed": True,
            "selected_candidate_rationale": "The selected tests skew heavily toward improvement behavior (`test_improvement*`) while only one test names adapter training directly. The visible evidence also includes an improvement-engine style snippet before the adapter-training implementation, so `improvement.py` is the most plausible first maintainer surface to inspect.",
            "anti_cheat_rationale": "This row provides a non-B Python action-taking target and helps reduce label-collapse risk. The answer remains grounded in prompt-visible snippets and test names rather than hidden path metadata.",
        },
    },
]

REJECTED = [
    {
        "row_id": "stage10110::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_25t16_28_28_019abbd8_55f2_7781_97b4_efce_models_cli_py_models_scripts_build_repo_graphs_py_models_scripts_preprocess_pdfs_bde13d0440_aug_1500000_8b46e7f662::python_implementation_vs_config",
        "reason": "Rejected for this support package. The config-vs-implementation geometry is a poor fit for the unresolved Mirrormind implementation-action frontier, and the singleton answer would lean too heavily on template prior rather than local maintainer evidence.",
    }
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
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


def snippet(text: str, limit: int = 220) -> str:
    clean = ' '.join(str(text).split())
    return clean if len(clean) <= limit else clean[: max(0, limit - 3)] + '...'


def prompt_for(row: dict[str, Any], options: list[tuple[str, str]]) -> str:
    surface = row.get('prompt_surface') if isinstance(row.get('prompt_surface'), dict) else {}
    pieces = [
        f"Language: {row.get('language_family')}",
        f"Template: {row.get('successor_template')}",
        f"Task: {surface.get('task_observation')}",
        'Evidence:',
    ]
    for idx, evidence in enumerate(surface.get('visible_evidence') or [], start=1):
        pieces.append(f"evidence_{idx}: {snippet(str(evidence))}")
    pieces.append('Options:')
    for label, value in options:
        pieces.append(f"{label}. {value}")
    pieces.append('Answer:')
    return '\n'.join(pieces) + '\n'


def candidate_value(choice: dict[str, Any]) -> str:
    cid = str(choice.get('candidate_id') or '')
    preview = snippet(str(choice.get('snippet_preview') or ''), limit=200)
    return f"candidate_{cid}: {preview}"


def rotate(values: list[str], shift: int) -> list[str]:
    return values[shift:] + values[:shift]


def selected_rows_by_id() -> dict[str, dict[str, Any]]:
    packet_rows = {str(row.get('row_id') or ''): row for row in load_jsonl(SOURCE_PACKET)}
    out: dict[str, dict[str, Any]] = {}
    for spec in SELECTED:
        row_id = spec['row_id']
        if row_id not in packet_rows:
            raise KeyError(f'missing_source_row::{row_id}')
        out[row_id] = packet_rows[row_id]
    return out


def build_support_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows = selected_rows_by_id()
    train_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    for spec in SELECTED:
        row = source_rows[spec['row_id']]
        surface = row['prompt_surface']
        choices = [choice for choice in (surface.get('candidate_choices') or []) if isinstance(choice, dict)]
        label_space = ['A', 'B', 'C', 'D'][: len(choices)]
        values = [candidate_value(choice) for choice in choices]
        choice_by_id = {str(choice.get('candidate_id') or ''): candidate_value(choice) for choice in choices}
        gold_value = choice_by_id[spec['gold_candidate_id']]
        hidden = row.get('hidden_metadata') if isinstance(row.get('hidden_metadata'), dict) else {}
        inventory_rows.append({
            'row_id': spec['row_id'],
            'language_family': row.get('language_family'),
            'repo_id': row.get('repo_id'),
            'successor_template': row.get('successor_template'),
            'support_family': spec['support_family'],
            'selected_candidate_id': spec['gold_candidate_id'],
            'selected_candidate_value': gold_value,
            'selected_tests': list(hidden.get('selected_tests') or []),
            'ai_review': spec['ai_review'],
            'candidate_ids': [str(choice.get('candidate_id') or '') for choice in choices],
            'candidate_values': values,
        })
        for shift in range(len(values)):
            ordered_values = rotate(values, shift)
            options = list(zip(label_space, ordered_values))
            label_by_value = {value: label for label, value in options}
            prompt = prompt_for(row, options)
            train_rows.append({
                'row_id': f"{spec['row_id']}::source_backed_support::perm_{shift:02d}",
                'semantic_key': f"source_backed_support::{spec['support_family']}::{row.get('language_family')}::perm_{shift:02d}",
                'language_family': row.get('language_family'),
                'route': 'KEEP_BOUNDED_DECODER',
                'objective_family': 'bounded_decoder_ce',
                'surface': 'real_session_shortcut_safe_successor',
                'task_type': str(row.get('successor_template') or ''),
                'split': 'train',
                'prompt_text': prompt,
                'input_text': prompt,
                'query_text': f"source_backed_support::{row.get('language_family')}::{row.get('successor_template')}::perm_{shift:02d}",
                'target_text': label_by_value[gold_value],
                'decoder_text': label_by_value[gold_value],
                'target_token_len': len(label_by_value[gold_value].encode('utf-8')),
                'loss_mask': {'decoder_ce': True},
                'expected_enabled_loss': 'decoder_ce',
                'disable_losses': [],
                'source_skill_area': 'real_session_shortcut_safe_successor',
                'source_stage': 10110,
                'source_row_id': spec['row_id'],
                'source_bundle_id': spec['row_id'],
                'standalone_projection_source': {
                    'projection_mode': 'direct_successor_choice_auxiliary',
                    'projection_stage': STAGE,
                    'original_return_protocol': surface.get('return_protocol'),
                    'gold_candidate_id': spec['gold_candidate_id'],
                    'gold_value': gold_value,
                    'opaque_options': [{'label': label, 'value': value} for label, value in options],
                    'selected_tests': list(hidden.get('selected_tests') or []),
                    'support_family': spec['support_family'],
                    'ai_review': spec['ai_review'],
                },
                'authority': {
                    'model_execution_authorized_next': False,
                    'decoder_ce_training_authorized_next': False,
                    'denoise_ce_training_authorized_next': False,
                    'runtime_authorized': False,
                    'source_emission_authorized': False,
                    'body_emission_authorized': False,
                    'gemma_execution_authorized_next': False,
                    'harness_execution_authorized_next': False,
                    'scoring_authorized_next': False,
                    'controller_complete_merge_authorized_next': False,
                    'promotion_ready': False,
                },
                'anti_cheat': {
                    'prompt_visible_only_review': True,
                    'source_backed_successor_train_only': True,
                    'permutation_balanced_labels': True,
                    'no_strict_eval_rows_moved_into_train': True,
                    'ai_review_completed_in_repo': True,
                    'not_for_primary_maintainer_claim': True,
                    'freeform_rows_excluded': True,
                    'support_family_specific': True,
                },
            })
    return train_rows, inventory_rows


def command(split_counts: dict[str, int]) -> list[str]:
    return [
        'env',
        f'TMPDIR={TMPDIR}',
        f'TEMP={TMPDIR}',
        f'TMP={TMPDIR}',
        'conda', 'run', '-n', 'trellis', 'python', str(TRAINER),
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
        '--max-train-rows', str(split_counts.get('train', 0)),
        '--max-eval-rows', '0',
        '--max-strict-rows', str(split_counts.get('strict_eval', 0)),
        '--max-steps', str(MAX_STEPS),
        '--batch-size', '2',
        '--learning-rate', LEARNING_RATE,
        '--max-encoder-tokens', '768',
        '--max-decoder-tokens', '8',
        '--decoder-ce-weight', '0.2',
        '--bounded-choice-aux-weight', '1.0',
        '--bounded-choice-aux-source', 'encoder_option_retrieval',
        '--structured-aux-weight', '0.0',
        '--denoise-weight', '0.0',
        '--eos-loss-weight', '4.0',
        '--enable-generation-audit',
        '--max-generation-rows', '16',
        '--max-generation-tokens', '8',
        '--require-loss-mask-enforcement-audit',
        '--allow-runtime-model-save-for-harness',
        '--runtime-model-save-dir', str(ROOT / RUNTIME_MODEL_DIR),
        '--initialize-from-runtime-model', str(INIT_RUNTIME),
        '--no-final-checkpoint-export',
        '--skip-final-model-save', '1',
        '--output-dir', str(ROOT / OUTPUT_DIR),
        '--run-id', RUN_ID,
    ]


def build() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    support_rows, inventory_rows = build_support_rows()
    seen = {str(row.get('row_id') or '') for row in base_rows}
    merged = list(base_rows)
    added = 0
    for row in support_rows:
        row_id = str(row.get('row_id') or '')
        if row_id in seen:
            continue
        seen.add(row_id)
        merged.append(row)
        added += 1
    write_jsonl(TRAIN_ROWS_JSONL, support_rows)
    write_jsonl(MANIFEST_JSONL, merged)
    split_counts = {'train': 0, 'strict_eval': 0, 'eval': 0, 'other': 0}
    language_counts: dict[str, int] = {}
    for row in merged:
        split = str(row.get('split') or '')
        split_counts[split if split in split_counts else 'other'] += 1
        lang = str(row.get('language_family') or '')
        language_counts[lang] = language_counts.get(lang, 0) + 1
    cmd = command(split_counts)
    inventory = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'selected_rows': inventory_rows,
        'rejected_rows': REJECTED,
        'train_rows_path': display(TRAIN_ROWS_JSONL),
        'base_manifest': display(BASE_MANIFEST),
        'strict_eval_unchanged': True,
    }
    request = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'warm_start_source_backed_action_support_ready',
        'manifest': display(MANIFEST_JSONL),
        'rows': len(merged),
        'split_counts': split_counts,
        'language_counts': dict(sorted(language_counts.items())),
        'frontloaded_focus_counts': {
            'source_backed_added': added,
            'by_support_family': {spec['support_family']: 2 for spec in SELECTED},
        },
        'source_manifests': {
            'base': display(BASE_MANIFEST),
            'support_inventory': display(INVENTORY_JSON),
            'support_train_rows': display(TRAIN_ROWS_JSONL),
        },
        'initialize_from_runtime_model': display(INIT_RUNTIME),
        'max_steps': MAX_STEPS,
        'learning_rate': LEARNING_RATE,
        'run_id': RUN_ID,
        'output_dir': OUTPUT_DIR,
        'required_honesty_gates': [
            'strict eval rows remain identical to stage10302/stage10303',
            'added rows come only from stage10110 source-backed successor packet and are train-only',
            'the repository_library config-vs-implementation row remains excluded due template-prior risk',
            'any gain must be described as source-backed support-family generalization, not as direct repair of heldout roots',
        ],
        'next_best_step': 'run one focused warm-start probe and check whether Python and web action-taking perspectives move without changing the strict eval set',
        'command': cmd,
    }
    write_json(INVENTORY_JSON, inventory)
    write_json(REQUEST_JSON, request)
    write_json(COMMAND_JSON, {'command': cmd, 'cwd': str(ROOT), 'env': 'trellis', 'tmpdir': str(TMPDIR)})
    write_json(SUMMARY, {
        'stage': STAGE,
        'passed': True,
        'request': display(REQUEST_JSON),
        'inventory': display(INVENTORY_JSON),
        'manifest': display(MANIFEST_JSONL),
        'rows': len(merged),
        'added_support_rows': added,
        'split_counts': split_counts,
    })
    return {
        'inventory': inventory,
        'request': request,
        'added_support_rows': added,
        'rows': len(merged),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    result = build()
    print(json.dumps({
        'stage': STAGE,
        'passed': True,
        'inventory': display(INVENTORY_JSON),
        'request': display(REQUEST_JSON),
        'added_support_rows': result['added_support_rows'],
        'rows': result['rows'],
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
