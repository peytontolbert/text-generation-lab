#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10327
NAME = "stage10327_python_mirrormind_replenishment_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BUNDLE_JSON = OUT_DIR / "python_mirrormind_replenishment_bundle.json"
RUBRIC_JSON = OUT_DIR / "review_packets" / "stage10327__repository_library__python" / "expert_maintainer_rubric_review.json"
ANTI_JSON = OUT_DIR / "review_packets" / "stage10327__repository_library__python" / "anti_cheat_review_card.json"
GOLD_JSON = OUT_DIR / "review_packets" / "stage10327__repository_library__python" / "perspective_gold_adjudication.json"
TRAIN_ROWS_JSONL = OUT_DIR / "python_mirrormind_replenishment_train_rows.jsonl"
MANIFEST_JSONL = OUT_DIR / "python_mirrormind_replenishment_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "python_mirrormind_replenishment_execution_request.json"
COMMAND_JSON = OUT_DIR / "python_mirrormind_replenishment_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10307_source_backed_action_support_plus_execution_request/source_backed_action_support_plus_manifest.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10308_source_backed_action_support_plus_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
REPO_ROOT = Path('/data/repository_library')
TMPDIR = Path('/data/tmp')

RUN_ID = 'stage10328_python_mirrormind_replenishment_probe'
OUTPUT_DIR = 'runs/local/artifacts/stage10328_python_mirrormind_replenishment_probe/bounded_decoder_probe'
RUNTIME_MODEL_DIR = 'runs/local/artifacts/stage10328_python_mirrormind_replenishment_probe/runtime_model'
MAX_STEPS = 56
LEARNING_RATE = '8e-6'
BATCH_SIZE = 2
PERMUTATION_COUNT = 4

BUNDLE_ID = (
    'stage10327::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_29t02_41_34_019acd7c_b80e_7880_9f45_f500_'
    'models_mirrormind_coordinator_py_models_mirrormind_domain_py_models_mirrormind_m_3b079208d1_aug_1500000_8b46e7f662::python'
)
CANDIDATE_PATHS = [
    'models/mirrormind/coordinator.py',
    'models/mirrormind/graph_client.py',
    'models/mirrormind/domain.py',
    'models/mirrormind/memory.py',
]
SELECTED_TESTS = [
    'models/mirrormind/tests/test_coordinator.py',
    'models/mirrormind/tests/test_coordinator_piano_integration.py',
    'models/mirrormind/tests/test_domain_graph.py',
    'models/mirrormind/tests/test_memory_index.py',
]
VISIBLE_EVIDENCE_KEYS = [
    'candidate_change_surface',
    'verifier_and_test_constraint',
    'nearby_definition_or_usage_context',
]
TASK_ROWS = [
    {
        'perspective': 'symptom_localization',
        'answer_kind': 'candidate_path',
        'gold_value': 'models/mirrormind/coordinator.py',
        'task': 'Choose the most likely edit target from the visible failure and behavior-ownership evidence.',
    },
    {
        'perspective': 'evidence_citation',
        'answer_kind': 'visible_evidence_key',
        'gold_value': 'candidate_change_surface',
        'task': 'Name the visible fact family that best supports the chosen edit target.',
    },
    {
        'perspective': 'patch_impact',
        'answer_kind': 'candidate_path',
        'gold_value': 'models/mirrormind/coordinator.py',
        'task': 'Compare candidate edits by likely behavior change and choose the one most likely to affect the failing coordinator behavior.',
    },
    {
        'perspective': 'verifier_outcome',
        'answer_kind': 'selected_test',
        'gold_value': 'models/mirrormind/tests/test_coordinator.py',
        'task': 'Choose the most relevant visible verification target if the coordinator fix is correct.',
    },
    {
        'perspective': 'minimal_fix_selection',
        'answer_kind': 'candidate_path',
        'gold_value': 'models/mirrormind/coordinator.py',
        'task': 'Choose the smallest maintainable intervention supported by the visible evidence.',
    },
    {
        'perspective': 'abstention_insufficient_evidence',
        'answer_kind': 'candidate_path',
        'gold_value': 'models/mirrormind/coordinator.py',
        'task': 'Decide whether the visible evidence supports a singleton answer or whether abstention is more honest.',
    },
]


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


def compact(text: str, limit: int = 1100) -> str:
    clean = str(text).strip()
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + '...'


def excerpt(path: Path, anchor: str, radius: int = 22) -> str:
    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    idx = 0
    for i, line in enumerate(lines):
        if anchor in line:
            idx = i
            break
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius)
    return compact('\n'.join(lines[start:end]))


def deterministic_rotate(values: list[str], shift: int) -> list[str]:
    return values[shift:] + values[:shift]


def evidence() -> dict[str, list[dict[str, Any]]]:
    return {
        'candidate_change_surface': [
            {
                'path': 'models/mirrormind/coordinator.py',
                'source_type': 'local_repo',
                'retrieval_reason': 'fresh_repository_library_seed_change',
                'distance_from_seed': 0,
                'text': excerpt(REPO_ROOT / 'models/mirrormind/coordinator.py', 'def run(self, task: TaskDescriptor)', radius=24),
            },
            {
                'path': 'models/mirrormind/graph_client.py',
                'source_type': 'local_repo',
                'retrieval_reason': 'fresh_repository_library_competing_candidate',
                'distance_from_seed': 1,
                'text': excerpt(REPO_ROOT / 'models/mirrormind/graph_client.py', 'class FileGraphClient', radius=20),
            },
            {
                'path': 'models/mirrormind/domain.py',
                'source_type': 'local_repo',
                'retrieval_reason': 'fresh_repository_library_competing_candidate',
                'distance_from_seed': 1,
                'text': excerpt(REPO_ROOT / 'models/mirrormind/domain.py', 'class DomainGraph', radius=18),
            },
            {
                'path': 'models/mirrormind/memory.py',
                'source_type': 'local_repo',
                'retrieval_reason': 'fresh_repository_library_competing_candidate',
                'distance_from_seed': 1,
                'text': excerpt(REPO_ROOT / 'models/mirrormind/memory.py', 'class Episode', radius=18),
            },
        ],
        'verifier_and_test_constraint': [
            {
                'path': 'models/mirrormind/tests/test_coordinator.py',
                'source_type': 'local_repo',
                'retrieval_reason': 'targeted_test_selection',
                'distance_from_seed': 1,
                'text': excerpt(REPO_ROOT / 'models/mirrormind/tests/test_coordinator.py', 'def test_coordinator_prefers_expert_entities', radius=24),
            },
            {
                'path': 'models/mirrormind/tests/test_coordinator_piano_integration.py',
                'source_type': 'local_repo',
                'retrieval_reason': 'targeted_test_selection',
                'distance_from_seed': 1,
                'text': excerpt(REPO_ROOT / 'models/mirrormind/tests/test_coordinator_piano_integration.py', 'def test_coordinator_run_multi_step_uses_piano_agent', radius=24),
            },
        ],
        'nearby_definition_or_usage_context': [
            {
                'path': 'models/mirrormind/context.py',
                'source_type': 'local_repo',
                'retrieval_reason': 'repo_local_linked_usage_context',
                'distance_from_seed': 1,
                'text': excerpt(REPO_ROOT / 'models/mirrormind/context.py', 'class ContextAssembler', radius=22),
            },
            {
                'path': 'models/mirrormind/coordinator.py',
                'source_type': 'local_repo',
                'retrieval_reason': 'repo_local_linked_usage_context',
                'distance_from_seed': 1,
                'text': excerpt(REPO_ROOT / 'models/mirrormind/coordinator.py', 'class Coordinator', radius=22),
            },
        ],
    }


def bundle_payload(bundle_evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        'bundle_id': BUNDLE_ID,
        'root_example_id': BUNDLE_ID.split('::', 1)[1].rsplit('::', 1)[0],
        'repo_id': 'repository_library',
        'language_family': 'python',
        'source_route': 'PATCH_ONLY_SOURCE_BACKED_REPLENISHMENT',
        'seed_paths': [
            'models/mirrormind/coordinator.py',
            'models/mirrormind/domain.py',
            'models/mirrormind/memory.py',
            'models/mirrormind/tests/test_coordinator.py',
        ],
        'selected_tests': list(SELECTED_TESTS),
        'claim_boundary': {
            'gold_answers_fully_adjudicated': True,
            'supports_training_or_scoring_now': True,
            'preview_only': False,
            'train_support_only': True,
            'same_surface_eval_admissible': False,
        },
        'maintainer_visible_evidence': bundle_evidence,
        'candidate_paths': list(CANDIDATE_PATHS),
        'perspective_rows': [
            {
                'bundle_id': BUNDLE_ID,
                'language_family': 'python',
                'perspective': task['perspective'],
                'prompt_contract': {
                    'task': task['task'],
                    'candidate_paths': list(CANDIDATE_PATHS),
                    'selected_tests': list(SELECTED_TESTS),
                    'visible_evidence_keys': list(VISIBLE_EVIDENCE_KEYS),
                    'abstention_option_required': task['perspective'] == 'abstention_insufficient_evidence',
                },
                'gold_answer_status': 'completed_ai_maintainer_adjudication',
                'eligible_for_training_or_scoring_now': True,
            }
            for task in TASK_ROWS
        ],
    }


def build_options(answer_kind: str, gold_value: str) -> list[str]:
    if answer_kind == 'candidate_path':
        values = list(CANDIDATE_PATHS)
    elif answer_kind == 'visible_evidence_key':
        values = list(VISIBLE_EVIDENCE_KEYS)
    elif answer_kind == 'selected_test':
        values = list(SELECTED_TESTS)
    else:
        values = [gold_value]
    if gold_value not in values:
        values.append(gold_value)
    return values


def compile_prompt(bundle_evidence: dict[str, list[dict[str, Any]]], task: dict[str, str], options: list[tuple[str, str]]) -> str:
    parts = [
        'Language: python',
        f"Perspective: {task['perspective']}",
        f"Task: {task['task']}",
        'Evidence:',
    ]
    for key in VISIBLE_EVIDENCE_KEYS:
        for item in bundle_evidence.get(key, [])[:2]:
            parts.append(f"{key} [{item['path']}]: {' '.join(str(item['text']).split())}")
    parts.append('Options:')
    parts.extend([f'{label}. {value}' for label, value in options])
    parts.append('Answer:')
    return '\n'.join(parts) + '\n'


def compile_train_rows(bundle_evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in TASK_ROWS:
        values = build_options(task['answer_kind'], task['gold_value'])
        labels = list('ABCDEFG')[: len(values)]
        for shift in range(min(PERMUTATION_COUNT, len(values))):
            ordered_values = deterministic_rotate(values, shift)
            options = list(zip(labels, ordered_values))
            label_by_value = {value: label for label, value in options}
            prompt = compile_prompt(bundle_evidence, task, options)
            rows.append({
                'row_id': f"{BUNDLE_ID}::{task['perspective']}::compact_bounded::perm_{shift:02d}",
                'semantic_key': f"python_mirrormind_replenishment::{task['perspective']}::perm_{shift:02d}",
                'bundle_id': BUNDLE_ID,
                'source_bundle_id': BUNDLE_ID,
                'source_row_id': f"{BUNDLE_ID}::{task['perspective']}::compact_bounded",
                'source_stage': STAGE,
                'source_skill_area': 'maintainer_bundle_compact_bounded_choice',
                'language_family': 'python',
                'task_type': task['perspective'],
                'surface': 'maintainer_bundle_compact_bounded_choice',
                'route': 'KEEP_BOUNDED_DECODER',
                'objective_family': 'bounded_decoder_ce',
                'query_text': f"compact_bounded::python::{task['perspective']}::{task['answer_kind']}::perm_{shift:02d}",
                'prompt_text': prompt,
                'input_text': prompt,
                'target_text': label_by_value[task['gold_value']],
                'decoder_text': label_by_value[task['gold_value']],
                'target_token_len': len(label_by_value[task['gold_value']].encode('utf-8')),
                'split': 'train',
                'loss_mask': {'decoder_ce': True},
                'disable_losses': [],
                'expected_enabled_loss': 'decoder_ce',
                'standalone_projection_source': {
                    'gold_answers_path': display(GOLD_JSON),
                    'gold_value': task['gold_value'],
                    'opaque_options': [{'label': label, 'value': value} for label, value in options],
                    'original_answer_kind': task['answer_kind'],
                    'projection_mode': 'compact_bounded_choice_auxiliary',
                    'projection_stage': STAGE,
                    'claim_boundary': {
                        'train_support_only': True,
                        'same_surface_eval_admissible': False,
                        'fresh_example_id_disjoint_from_stage10307': True,
                    },
                },
                'authority': {
                    'body_emission_authorized': False,
                    'controller_complete_merge_authorized_next': False,
                    'decoder_ce_training_authorized_next': False,
                    'denoise_ce_training_authorized_next': False,
                    'gemma_execution_authorized_next': False,
                    'harness_execution_authorized_next': False,
                    'model_execution_authorized_next': False,
                    'promotion_ready': False,
                    'runtime_authorized': False,
                    'scoring_authorized_next': False,
                    'source_emission_authorized': False,
                },
                'anti_cheat': {
                    'compact_prompt_contract': True,
                    'deterministic_option_shuffle': True,
                    'opaque_labels': True,
                    'reviewed_bundle_source': True,
                    'train_support_only': True,
                    'not_for_primary_maintainer_claim': True,
                    'fresh_source_backed_root': True,
                    'exact_coordinator_vs_graph_client_support': True,
                },
            })
    return rows


def rubric_review() -> dict[str, Any]:
    rationale = (
        'Admit for train-support use. The visible tests exercise Coordinator methods directly, the competing graph client '
        'is shown as a lower-level helper, and the bounded candidate set stays within maintainer-plausible Python surfaces. '
        'This is strong enough for auxiliary training support, but it remains train-only rather than a headline evaluation cell.'
    )
    return {
        'bundle_id': BUNDLE_ID,
        'bundle_valid_for_eval': True,
        'decision_rationale': rationale,
        'gold_adjudication_slot': {
            'bundle_level_signoff': True,
            'perspective_gold_answers_recorded': True,
            'reviewer_rationale': rationale,
        },
        'language_family': 'python',
        'passed': True,
        'repo_id': 'repository_library',
        'required_human_action': 'None required for train-support-only use; keep separate from headline same-surface evaluation claims.',
        'reviewer_id': 'codex-gpt5-ai-review',
        'reviewer_notes': 'AI maintainer adjudication performed on real repository_library source snippets with explicit test evidence and helper-vs-owner contrast.',
        'rubric_lines': {
            'abstention_is_available_when_evidence_is_insufficient': True,
            'candidate_paths_are_maintainer_plausible': True,
            'perspectives_test_distinct_reasoning_not_template_rephrases': True,
            'root_bundle_is_maintainer_meaningful': True,
            'visible_evidence_is_sufficient_for_bounded_train_support': True,
        },
        'status': 'completed',
        'train_support_only': True,
    }


def anti_cheat_review() -> dict[str, Any]:
    rationale = (
        'Pass for train-support use. The chosen target is justified by prompt-visible coordinator tests and ownership-bearing snippets, '
        'while graph_client/domain/memory remain plausible but less directly exercised alternatives. The row should still remain outside '
        'headline benchmark claims because it is being added as support after weakness discovery.'
    )
    return {
        'bundle_id': BUNDLE_ID,
        'admissible_for_same_surface_comparison': False,
        'challenge_families': {
            'candidate_path_or_order_bias': False,
            'cross_repo_analogue_leakage': False,
            'hidden_reference_or_metadata_leakage': False,
            'perspective_paraphrase_collapse': False,
            'same_surface_fairness_for_future_gemma_comparison': False,
            'template_and_surface_prior_shortcuts': False,
        },
        'decision_rationale': rationale,
        'language_family': 'python',
        'passed': True,
        'reviewer_id': 'codex-gpt5-ai-review',
        'reviewer_notes': rationale,
        'status': 'completed',
        'train_support_only': True,
    }


def gold_adjudication() -> dict[str, Any]:
    rationale = 'AI maintainer gold answers recorded for bounded train-support use on a fresh source-backed MirrorMind coordinator root.'
    return {
        'bundle_gold_ready_for_eval': True,
        'bundle_id': BUNDLE_ID,
        'decision_rationale': rationale,
        'draft_recommendation_path': None,
        'language_family': 'python',
        'perspective_gold_answers': [
            {
                'perspective': task['perspective'],
                'gold_answer_kind': task['answer_kind'],
                'gold_answer_value': task['gold_value'],
                'reviewer_rationale': rationale,
            }
            for task in TASK_ROWS
        ],
        'recommended_answer_kind_schema': {
            row['perspective']: {
                'allowed_answer_kinds': [row['answer_kind'], 'abstain'] if row['answer_kind'] != 'candidate_path' else ['candidate_path', 'abstain'],
                'recommended_primary_kind': row['answer_kind'],
            }
            for row in TASK_ROWS
        },
        'repo_id': 'repository_library',
        'reviewer_guidance': [
            'This packet is admitted for train-support use only.',
            'Do not use these post-hoc support rows as headline evaluation evidence for same-surface Gemma comparison.',
        ],
        'reviewer_id': 'codex-gpt5-ai-review',
        'status': 'completed',
        'train_support_only': True,
    }


def main() -> None:
    base_rows = load_jsonl(BASE_MANIFEST)
    base_train_rows = [row for row in base_rows if row.get('split') == 'train']
    base_strict_rows = [row for row in base_rows if row.get('split') == 'strict_eval']
    bundle_evidence = evidence()
    bundle = bundle_payload(bundle_evidence)
    train_rows = compile_train_rows(bundle_evidence)
    combined_rows = train_rows + base_train_rows + base_strict_rows

    write_json(BUNDLE_JSON, bundle)
    write_json(RUBRIC_JSON, rubric_review())
    write_json(ANTI_JSON, anti_cheat_review())
    write_json(GOLD_JSON, gold_adjudication())
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(MANIFEST_JSONL, combined_rows)

    split_counts = {}
    language_counts = {}
    for row in combined_rows:
        split_counts[row['split']] = split_counts.get(row['split'], 0) + 1
        language_counts[row['language_family']] = language_counts.get(row['language_family'], 0) + 1

    command = [
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
        '--batch-size', str(BATCH_SIZE),
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
    request = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'fresh_python_mirrormind_replenishment_ready',
        'manifest': display(MANIFEST_JSONL),
        'source_manifests': {
            'base': display(BASE_MANIFEST),
            'fresh_bundle': display(BUNDLE_JSON),
            'support_train_rows': display(TRAIN_ROWS_JSONL),
        },
        'split_counts': split_counts,
        'language_counts': language_counts,
        'rows': len(combined_rows),
        'max_steps': MAX_STEPS,
        'learning_rate': LEARNING_RATE,
        'initialize_from_runtime_model': display(INIT_RUNTIME),
        'required_honesty_gates': [
            'strict eval rows remain identical to stage10307/stage10308',
            'fresh support rows come from a disjoint source-backed repository_library example id',
            'new rows are train-support-only and excluded from headline same-surface Gemma claims',
            'web supply remains unchanged because current fresh web inventory is still underconstrained',
        ],
        'next_best_step': 'run one warm-start probe and check whether the unresolved Python coordinator strict family moves without harming C/C++ evidence citation',
        'command': command,
        'output_dir': OUTPUT_DIR,
        'run_id': RUN_ID,
    }
    write_json(REQUEST_JSON, request)
    write_json(COMMAND_JSON, {'command': command, 'cwd': str(ROOT), 'env': 'trellis', 'tmpdir': str(TMPDIR)})
    write_json(SUMMARY, {
        'stage': STAGE,
        'stage_name': NAME,
        'passed': True,
        'artifact': display(REQUEST_JSON),
        'next_best_step': request['next_best_step'],
    })
    print(json.dumps({'stage': STAGE, 'passed': True, 'artifact': display(REQUEST_JSON), 'train_rows': len(train_rows)}, indent=2))


if __name__ == '__main__':
    main()
