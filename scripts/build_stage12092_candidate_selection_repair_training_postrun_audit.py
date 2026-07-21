#!/usr/bin/env python3
"""Audit Stage12091 candidate-selection repair training runtime."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
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
STAGE = 12092
NAME = 'stage12092_candidate_selection_repair_training_postrun_audit'
OUT = ART / NAME
SUMMARY = OUT / 'candidate_selection_repair_training_postrun_audit.json'
TRANSITION_ROWS = ART / 'stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'
RUNTIMES = {
    'stage11924_transition_listwise_head_only': ART / 'stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json',
    'stage12083_next_action_repair_training': ART / 'stage12083_next_action_repair_training_probe/runtime_model/runtime_model_bundle.json',
    'stage12091_candidate_selection_repair_training': ART / 'stage12091_candidate_selection_repair_training_probe/runtime_model/runtime_model_bundle.json',
}
PROTECTED_ROWSETS = {
    'residual_bank': ART / 'stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl',
    'filtered_strict': ART / 'stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl',
    'old_canary_strict': ART / 'stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl',
    'filtered_validation': ART / 'stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl',
    'old_canary_validation': ART / 'stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl',
    'verifier_grounded_source_heldout_smoke': ART / 'stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_successor_rows.jsonl',
}
TRANSITION_SCORER = 'encoder_option_retrieval_semantic_candidate_head'
COMPACT_SCORER = 'encoder_option_retrieval_evidence_judgment_head'

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


def metric(card: dict[str, Any]) -> dict[str, Any]:
    return {
        'rows': card.get('rows'),
        'correct': card.get('constrained_choice_correct'),
        'accuracy': card.get('constrained_choice_top1_accuracy'),
        'coverage': card.get('constrained_choice_coverage'),
        'miss_count': sum(1 for row in card.get('row_cards') or [] if row.get('constrained_choice_match') is not True),
    }


def row_group_value(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is not None:
        return str(value)
    if key == 'task_type':
        rid = str(row.get('row_id') or '')
        for suffix in ('next_action', 'candidate_selection', 'verifier_transition', 'continue_or_stop'):
            if rid.endswith('::' + suffix) or ('::' + suffix + '::') in rid:
                return 'transition_' + suffix
    return 'unknown'


def grouped(card: dict[str, Any], key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in card.get('row_cards') or []:
        buckets.setdefault(row_group_value(row, key), []).append(row)
    out = {}
    for name, rows in sorted(buckets.items()):
        correct = sum(1 for row in rows if row.get('constrained_choice_match') is True)
        out[name] = {'rows': len(rows), 'correct': correct, 'accuracy': correct / len(rows) if rows else None}
    return out


def changed_rows(base_card: dict[str, Any], post_card: dict[str, Any]) -> dict[str, Any]:
    base = {r['row_id']: r for r in base_card.get('row_cards') or []}
    post = {r['row_id']: r for r in post_card.get('row_cards') or []}
    gained, lost = [], []
    for rid, brow in base.items():
        prow = post.get(rid)
        if not prow:
            continue
        if brow.get('constrained_choice_match') is not True and prow.get('constrained_choice_match') is True:
            gained.append(rid)
        elif brow.get('constrained_choice_match') is True and prow.get('constrained_choice_match') is not True:
            lost.append(rid)
    return {'gained': gained, 'lost': lost, 'gain_count': len(gained), 'loss_count': len(lost), 'net': len(gained) - len(lost)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    transition_rows = [normalize_row(r) for r in read_jsonl(TRANSITION_ROWS)]
    protected = {name: [normalize_row(r) for r in read_jsonl(path)] for name, path in PROTECTED_ROWSETS.items()}
    results: dict[str, Any] = {}
    init_cards: dict[str, Any] = {}
    transition_cards: dict[str, Any] = {}

    for runtime_name, runtime_path in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime_path)
        init_cards[runtime_name] = init_card
        card = _write_bounded_choice_eval_audit(
            OUT / runtime_name,
            model=model,
            rows=transition_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name='transition_projection__semantic_candidate_head',
            bounded_choice_aux_source=TRANSITION_SCORER,
            eval_batch_size=8,
        )
        transition_cards[runtime_name] = card
        runtime_results: dict[str, Any] = {
            'transition_projection_routed': metric(card),
            'transition_by_language': grouped(card, 'language_family'),
            'transition_by_task': grouped(card, 'task_type'),
        }
        for name, rows in protected.items():
            pcard = _write_bounded_choice_eval_audit(
                OUT / runtime_name,
                model=model,
                rows=rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=16,
                split_name=f'protected__{name}__evidence_judgment_head',
                bounded_choice_aux_source=COMPACT_SCORER,
                eval_batch_size=8,
            )
            runtime_results[f'protected::{name}'] = metric(pcard)
        results[runtime_name] = runtime_results
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    base = results['stage11924_transition_listwise_head_only']
    next_diag = results['stage12083_next_action_repair_training']
    post = results['stage12091_candidate_selection_repair_training']
    task = post['transition_by_task']
    gates = {
        'transition_projection_improves_stage11924': (post['transition_projection_routed'].get('correct') or 0) > 364,
        'transition_projection_beats_gemma_386': (post['transition_projection_routed'].get('correct') or 0) > 386,
        'transition_next_action_preserved_from_stage12083': task['transition_next_action']['correct'] >= 59,
        'transition_candidate_selection_restored_to_stage11924': task['transition_candidate_selection']['correct'] >= 89,
        'transition_continue_or_stop_preserved': task['transition_continue_or_stop']['correct'] >= 128,
        'transition_verifier_transition_preserved': task['transition_verifier_transition']['correct'] >= 96,
        'filtered_strict_preserved': post['protected::filtered_strict'].get('correct') == 22,
        'old_canary_strict_preserved': post['protected::old_canary_strict'].get('correct') == 23,
        'filtered_validation_preserved': (post['protected::filtered_validation'].get('correct') or 0) >= 20,
        'old_canary_validation_preserved': (post['protected::old_canary_validation'].get('correct') or 0) >= 21,
        'residual_preserved': (post['protected::residual_bank'].get('correct') or 0) >= 7,
        'smoke_preserved': (post['protected::verifier_grounded_source_heldout_smoke'].get('correct') or 0) >= 6,
    }
    protected_names = [
        'filtered_strict_preserved',
        'old_canary_strict_preserved',
        'filtered_validation_preserved',
        'old_canary_validation_preserved',
        'residual_preserved',
        'smoke_preserved',
    ]
    protected_preserved = all(gates[name] for name in protected_names)
    lane_preserved = (
        gates['transition_next_action_preserved_from_stage12083']
        and gates['transition_candidate_selection_restored_to_stage11924']
        and gates['transition_continue_or_stop_preserved']
        and gates['transition_verifier_transition_preserved']
    )
    if protected_preserved and lane_preserved and gates['transition_projection_beats_gemma_386']:
        decision = 'stage12091_promotable_transition_gemma_win_candidate'
    elif protected_preserved and lane_preserved and gates['transition_projection_improves_stage11924']:
        decision = 'stage12091_transition_frontier_gain_candidate'
    elif protected_preserved and lane_preserved:
        decision = 'stage12091_lane_repair_retention_no_frontier_gain'
    else:
        decision = 'reject_stage12091_keep_stage11924_selected_transition_frontier'

    changes_vs_11924 = changed_rows(transition_cards['stage11924_transition_listwise_head_only'], transition_cards['stage12091_candidate_selection_repair_training'])
    changes_vs_12083 = changed_rows(transition_cards['stage12083_next_action_repair_training'], transition_cards['stage12091_candidate_selection_repair_training'])
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now(),
        'decision': decision,
        'device': str(DEVICE),
        'route_policy': {'transition_projection_rows': TRANSITION_SCORER, 'compact_protected_rows': COMPACT_SCORER},
        'gates': gates,
        'results': results,
        'transition_changes_vs_stage11924': changes_vs_11924,
        'transition_changes_vs_stage12083': changes_vs_12083,
        'runtime_initialization': init_cards,
        'source_artifacts': {
            'transition_rows': rel(TRANSITION_ROWS),
            'runtimes': {name: rel(path) for name, path in RUNTIMES.items()},
            'protected_rowsets': {name: rel(path) for name, path in PROTECTED_ROWSETS.items()},
            'stage12090_request': 'runs/summaries/stage12090_candidate_selection_repair_training_request.json',
        },
        'outputs': {'summary': rel(SUMMARY), 'audit_dir': rel(OUT), 'summary_mirror': f'runs/summaries/{NAME}.json'},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f'{NAME}.json')
    print(json.dumps({
        'decision': decision,
        'gates': gates,
        'stage11924_transition': base['transition_projection_routed'],
        'stage12083_transition': next_diag['transition_projection_routed'],
        'stage12091_transition': post['transition_projection_routed'],
        'stage11924_by_task': base['transition_by_task'],
        'stage12083_by_task': next_diag['transition_by_task'],
        'stage12091_by_task': post['transition_by_task'],
        'changes_vs_stage11924': changes_vs_11924,
        'changes_vs_stage12083': changes_vs_12083,
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
