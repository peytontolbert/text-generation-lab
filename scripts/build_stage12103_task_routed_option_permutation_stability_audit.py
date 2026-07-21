#!/usr/bin/env python3
"""Option permutation stability audit for the Stage12099 routed transition policy."""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ART = ROOT / 'runs/local/artifacts'
SUMMARIES = ROOT / 'runs/summaries'
STAGE = 12103
NAME = 'stage12103_task_routed_option_permutation_stability_audit'
OUT = ART / NAME
SUMMARY = OUT / 'task_routed_option_permutation_stability_audit.json'
PERMUTED_ROWS = OUT / 'task_routed_transition_permuted_rows.jsonl'
TRANSITION_ROWS = ART / 'stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'
ROUTE_PLAN = ROOT / 'runs/summaries/stage12102_task_routed_gap_targeted_data_plan.json'
RUNTIMES = {
    'stage11924_semantic': ART / 'stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json',
    'stage12083_semantic': ART / 'stage12083_next_action_repair_training_probe/runtime_model/runtime_model_bundle.json',
    'stage12096_composite': ART / 'stage12096_candidate_head_only_candidate_selection_probe/runtime_model/runtime_model_bundle.json',
}
SCORERS = {
    'stage11924_semantic': 'encoder_option_retrieval_semantic_candidate_head',
    'stage12083_semantic': 'encoder_option_retrieval_semantic_candidate_head',
    'stage12096_composite': 'encoder_option_retrieval_semantic_plus_transition_candidate_head',
}
ROUTE_POLICY = {
    'transition_candidate_selection': 'stage12096_composite',
    'transition_next_action': 'stage12083_semantic',
    'transition_continue_or_stop': 'stage11924_semantic',
    'transition_verifier_transition': 'stage11924_semantic',
}
LABELS = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
PERMUTATIONS_PER_ROW = 3

torch.set_num_threads(max(1, int(os.environ.get('AGENTKERNEL_EVAL_THREADS', '8'))))
try:
    torch.set_num_interop_threads(max(1, min(4, int(os.environ.get('AGENTKERNEL_EVAL_THREADS', '8')))))
except RuntimeError:
    pass
DEVICE = torch.device(os.environ.get('AGENTKERNEL_EVAL_DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu'))


def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + '\n')


def task_type(row: dict[str, Any]) -> str:
    value = row.get('task_type')
    if value:
        return str(value)
    rid = str(row.get('row_id') or '')
    for suffix in ('next_action', 'candidate_selection', 'verifier_transition', 'continue_or_stop'):
        if rid.endswith('::' + suffix) or ('::' + suffix + '::') in rid:
            return 'transition_' + suffix
    return 'unknown'


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    source = dict(out.get('standalone_projection_source') or {})
    source.setdefault('opaque_options', out.get('opaque_options') or [])
    out['standalone_projection_source'] = source
    if not isinstance(out.get('target'), dict):
        label = out.get('bounded_choice_target_label') or out.get('target_label') or out.get('target_text')
        out['target'] = {'decoder_text': out.get('decoder_text') or label, 'bounded_choice_target_label': label}
    out.setdefault('loss_mask', {'decoder_ce': True, 'bounded_choice_aux': True})
    return out


def option_identity(opt: dict[str, Any]) -> str:
    return json.dumps({k: v for k, v in opt.items() if k != 'label'}, sort_keys=True, separators=(',', ':'))


def option_line(opt: dict[str, Any]) -> str:
    pieces = [
        f"{opt['label']}: role={opt.get('role', '')}",
        f"artifact_type={opt.get('artifact_type', '')}",
        f"value={opt.get('value', '')}",
    ]
    evidence_ids = opt.get('evidence_ids') or []
    if evidence_ids:
        pieces.append('evidence_ids=' + ','.join(map(str, evidence_ids)))
    return '; '.join(pieces)


def rerender_prompt(text: str, options: list[dict[str, Any]]) -> str:
    marker = '\nCANDIDATES\n'
    question_marker = '\n\nQUESTION\n'
    if marker not in text or question_marker not in text:
        raise ValueError('prompt_missing_candidates_or_question_marker')
    prefix, rest = text.split(marker, 1)
    _old, suffix = rest.split(question_marker, 1)
    return prefix + marker + '\n'.join(option_line(opt) for opt in options) + question_marker + suffix


def permute_row(row: dict[str, Any], perm_index: int) -> dict[str, Any]:
    out = json.loads(json.dumps(row))
    options = [dict(opt) for opt in ((row.get('standalone_projection_source') or {}).get('opaque_options') or row.get('opaque_options') or [])]
    if len(options) < 2:
        raise ValueError('cannot_permute_singleton_options')
    old_target = str((row.get('target') or {}).get('bounded_choice_target_label') or row.get('bounded_choice_target_label') or row.get('target_label') or row.get('target_text'))
    target_identity = None
    for opt in options:
        if str(opt.get('label')) == old_target:
            target_identity = option_identity(opt)
            break
    if target_identity is None:
        raise ValueError('target_option_not_found')
    seed = int(hashlib.sha256(f"{row['row_id']}::{perm_index}".encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    rng.shuffle(options)
    new_options = []
    new_target = None
    for idx, opt in enumerate(options):
        new = dict(opt)
        new['label'] = LABELS[idx]
        if option_identity(opt) == target_identity:
            new_target = new['label']
        new_options.append(new)
    if new_target is None:
        raise ValueError('new_target_missing_after_permutation')
    out['row_id'] = f"{row['row_id']}::stage12103_perm{perm_index}"
    out['stage12103_original_row_id'] = row['row_id']
    out['stage12103_permutation_index'] = perm_index
    out['stage12103_original_target_label'] = old_target
    out['stage12103_new_target_label'] = new_target
    out['opaque_options'] = new_options
    source = dict(out.get('standalone_projection_source') or {})
    source['opaque_options'] = new_options
    source['gold_label'] = new_target
    source['gold_value'] = new_target
    out['standalone_projection_source'] = source
    out['bounded_choice_target_label'] = new_target
    out['target_label'] = new_target
    out['target_text'] = new_target
    out['decoder_text'] = new_target
    out['target'] = {'bounded_choice_target_label': new_target, 'decoder_text': new_target, 'semantic_value': new_target}
    for key in ('input_text', 'prompt_text'):
        if out.get(key):
            out[key] = rerender_prompt(str(out[key]), new_options)
    anti = dict(out.get('anti_cheat') or {})
    anti.update({
        'deterministic_option_shuffle': True,
        'stage12103_option_permutation_audit': True,
        'target_label_not_visible_before_options': True,
    })
    out['anti_cheat'] = anti
    return out


def load_runtime(path: Path):
    bundle = read_json(path)
    metadata = bundle['metadata']
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(metadata['model_config']))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(path, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata['tokenizer_json'])), Path(str(metadata['tokenizer_config'])))
    return model, tokenizer, init_card


def metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    correct = sum(1 for row in rows if row.get('constrained_choice_match') is True)
    return {'rows': len(rows), 'correct': correct, 'accuracy': correct / len(rows) if rows else None, 'miss_count': len(rows) - correct}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    route_plan = read_json(ROUTE_PLAN)
    base_rows = [normalize_row(row) for row in read_jsonl(TRANSITION_ROWS)]
    permuted_rows: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    for row in base_rows:
        for perm_index in range(PERMUTATIONS_PER_ROW):
            try:
                permuted_rows.append(permute_row(row, perm_index))
            except Exception as exc:
                blocked.append({'row_id': row.get('row_id', ''), 'error': str(exc)})
    write_jsonl(PERMUTED_ROWS, permuted_rows)

    cards_by_route: dict[str, dict[str, dict[str, Any]]] = {}
    init_cards: dict[str, Any] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        rows_for_route = [row for row in permuted_rows if ROUTE_POLICY.get(task_type(row)) == runtime_name]
        model, tokenizer, init_card = load_runtime(runtime_path)
        init_cards[runtime_name] = init_card
        card = _write_bounded_choice_eval_audit(
            OUT / runtime_name,
            model=model,
            rows=rows_for_route,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=f'permuted_transition__{runtime_name}',
            bounded_choice_aux_source=SCORERS[runtime_name],
            eval_batch_size=8,
        )
        cards_by_route[runtime_name] = {row['row_id']: row for row in card.get('row_cards') or []}
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    routed_cards: list[dict[str, Any]] = []
    missing = []
    for row in permuted_rows:
        source = ROUTE_POLICY.get(task_type(row))
        card = cards_by_route.get(source, {}).get(row['row_id'])
        if card is None:
            missing.append({'row_id': row['row_id'], 'route_source': str(source)})
            continue
        card = dict(card)
        opts_by_label = {str(opt.get('label')): opt for opt in (row.get('opaque_options') or [])}
        pred_opt = opts_by_label.get(str(card.get('constrained_choice_top1_label')))
        target_opt = opts_by_label.get(str(card.get('bounded_choice_target_label') or card.get('target_text')))
        card['stage12103_predicted_option_identity'] = option_identity(pred_opt) if pred_opt else None
        card['stage12103_target_option_identity'] = option_identity(target_opt) if target_opt else None
        card['stage12103_predicted_option_value'] = pred_opt.get('value') if pred_opt else None
        card['stage12103_target_option_value'] = target_opt.get('value') if target_opt else None
        card['stage12103_route_source'] = source
        card['stage12103_original_row_id'] = row['stage12103_original_row_id']
        card['stage12103_permutation_index'] = row['stage12103_permutation_index']
        routed_cards.append(card)

    per_original: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in routed_cards:
        per_original[card['stage12103_original_row_id']].append(card)
    stable_rows = 0
    majority_correct = 0
    unanimous_correct = 0
    unstable_examples = []
    for original, cards in per_original.items():
        preds = [str(card.get('stage12103_predicted_option_identity')) for card in cards]
        pred_values = [str(card.get('stage12103_predicted_option_value')) for card in cards]
        corrects = [card.get('constrained_choice_match') is True for card in cards]
        if len(set(preds)) == 1:
            stable_rows += 1
        else:
            unstable_examples.append({'row_id': original, 'predicted_option_values': pred_values, 'predicted_option_identities': preds, 'corrects': corrects})
        if sum(corrects) >= 2:
            majority_correct += 1
        if all(corrects) and len(corrects) == PERMUTATIONS_PER_ROW:
            unanimous_correct += 1

    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in routed_cards:
        by_task[task_type(card)].append(card)
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now(),
        'decision': 'option_permutation_stability_passed' if (
            not blocked
            and not missing
            and majority_correct >= 375
            and stable_rows / len(per_original) >= 0.90
        ) else 'option_permutation_stability_failed_or_diagnostic',
        'device': str(DEVICE),
        'route_policy': ROUTE_POLICY,
        'permutations_per_row': PERMUTATIONS_PER_ROW,
        'row_counts': {'base_rows': len(base_rows), 'permuted_rows': len(permuted_rows), 'blocked_rows': len(blocked), 'missing_route_cards': len(missing)},
        'stability': {
            'stable_semantic_prediction_rows': stable_rows,
            'total_original_rows': len(per_original),
            'stable_semantic_prediction_rate': stable_rows / len(per_original) if per_original else None,
            'majority_correct_rows': majority_correct,
            'unanimous_correct_rows': unanimous_correct,
            'majority_correct_accuracy': majority_correct / len(per_original) if per_original else None,
            'unanimous_correct_accuracy': unanimous_correct / len(per_original) if per_original else None,
        },
        'permuted_score': metric(routed_cards),
        'permuted_by_task': {name: metric(rows) for name, rows in sorted(by_task.items())},
        'requirements_from_stage12102': route_plan['confirmation_before_claim']['stage12103_option_permutation_stability_audit'],
        'blocked': blocked[:50],
        'missing': missing[:50],
        'unstable_examples': unstable_examples[:50],
        'runtime_initialization': init_cards,
        'source_artifacts': {
            'transition_rows': rel(TRANSITION_ROWS),
            'stage12102_plan': rel(ROUTE_PLAN),
            'runtimes': {name: rel(path) for name, path in RUNTIMES.items()},
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': f'runs/summaries/{NAME}.json',
            'permuted_rows': rel(PERMUTED_ROWS),
            'audit_dir': rel(OUT),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f'{NAME}.json')
    print(json.dumps({
        'decision': summary['decision'],
        'row_counts': summary['row_counts'],
        'stability': summary['stability'],
        'permuted_score': summary['permuted_score'],
        'permuted_by_task': summary['permuted_by_task'],
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
