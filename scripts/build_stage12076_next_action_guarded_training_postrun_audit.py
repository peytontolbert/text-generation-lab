#!/usr/bin/env python3
"""Audit Stage12075 next-action guarded training runtime."""
from __future__ import annotations

import json, os, shutil, sys, time
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
STAGE = 12076
NAME = 'stage12076_next_action_guarded_training_postrun_audit'
OUT = ART / NAME
SUMMARY = OUT / 'next_action_guarded_training_postrun_audit.json'
TRANSITION_ROWS = ART / 'stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'
RUNTIMES = {
    'stage11507_selected_frontier': ART / 'stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json',
    'stage11924_transition_listwise_head_only': ART / 'stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json',
    'stage12059_guarded_transition_training': ART / 'stage12059_guarded_transition_training_probe/runtime_model/runtime_model_bundle.json',
    'stage12075_next_action_guarded_training': ART / 'stage12075_next_action_guarded_training_probe/runtime_model/runtime_model_bundle.json',
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
    return {'gained': gained, 'lost': lost, 'gain_count': len(gained), 'loss_count': len(lost), 'net': len(gained)-len(lost)}


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

    previous = results['stage11924_transition_listwise_head_only']
    stage12059 = results['stage12059_guarded_transition_training']
    postrun = results['stage12075_next_action_guarded_training']
    next_action_prev = previous['transition_by_task']['transition_next_action']['correct']
    next_action_post = postrun['transition_by_task']['transition_next_action']['correct']
    gates = {
        'transition_projection_retains_stage11924_baseline': (postrun['transition_projection_routed'].get('correct') or 0) >= 364,
        'transition_projection_improves_stage11924_baseline': (postrun['transition_projection_routed'].get('correct') or 0) > 364,
        'transition_projection_beats_gemma_386': (postrun['transition_projection_routed'].get('correct') or 0) > 386,
        'transition_next_action_improves_stage11924': next_action_post > next_action_prev,
        'transition_next_action_beats_51': next_action_post > 51,
        'filtered_strict_preserved': postrun['protected::filtered_strict'].get('correct') == 22,
        'old_canary_strict_preserved': postrun['protected::old_canary_strict'].get('correct') == 23,
        'filtered_validation_preserved': (postrun['protected::filtered_validation'].get('correct') or 0) >= 20,
        'old_canary_validation_preserved': (postrun['protected::old_canary_validation'].get('correct') or 0) >= 21,
        'residual_preserved': (postrun['protected::residual_bank'].get('correct') or 0) >= 7,
        'smoke_preserved': (postrun['protected::verifier_grounded_source_heldout_smoke'].get('correct') or 0) >= 6,
    }
    protected_names = ['filtered_strict_preserved','old_canary_strict_preserved','filtered_validation_preserved','old_canary_validation_preserved','residual_preserved','smoke_preserved']
    protected_preserved = all(gates[n] for n in protected_names)
    if protected_preserved and gates['transition_projection_beats_gemma_386']:
        decision = 'stage12075_promotable_transition_gemma_win_candidate'
    elif protected_preserved and gates['transition_projection_improves_stage11924_baseline'] and gates['transition_next_action_improves_stage11924']:
        decision = 'stage12075_transition_frontier_gain_candidate'
    elif protected_preserved and gates['transition_projection_retains_stage11924_baseline']:
        decision = 'stage12075_retention_candidate_no_frontier_gain'
    else:
        decision = 'reject_stage12075_keep_stage11924_selected_transition_frontier'

    changes = changed_rows(transition_cards['stage11924_transition_listwise_head_only'], transition_cards['stage12075_next_action_guarded_training'])
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now(),
        'decision': decision,
        'device': str(DEVICE),
        'route_policy': {'transition_projection_rows': TRANSITION_SCORER, 'compact_protected_rows': COMPACT_SCORER},
        'gates': gates,
        'results': results,
        'transition_changes_vs_stage11924': changes,
        'stage12059_reference': stage12059['transition_projection_routed'],
        'runtime_initialization': init_cards,
        'source_artifacts': {
            'transition_rows': rel(TRANSITION_ROWS),
            'runtimes': {name: rel(path) for name, path in RUNTIMES.items()},
            'protected_rowsets': {name: rel(path) for name, path in PROTECTED_ROWSETS.items()},
            'stage12074_request': 'runs/summaries/stage12074_next_action_guarded_training_request.json',
        },
        'outputs': {'summary': rel(SUMMARY), 'audit_dir': rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f'{NAME}.json')
    print(json.dumps({
        'decision': decision,
        'gates': gates,
        'stage11924_transition': previous['transition_projection_routed'],
        'stage12075_transition': postrun['transition_projection_routed'],
        'stage11924_next_action': previous['transition_by_task']['transition_next_action'],
        'stage12075_next_action': postrun['transition_by_task']['transition_next_action'],
        'changes': changes,
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
