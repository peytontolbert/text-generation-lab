#!/usr/bin/env python3
"""Audit Stage12096 candidate-head-only transition diagnostic."""
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
STAGE = 12097
NAME = 'stage12097_candidate_head_only_candidate_selection_postrun_audit'
OUT = ART / NAME
SUMMARY = OUT / 'candidate_head_only_candidate_selection_postrun_audit.json'
TRANSITION_ROWS = ART / 'stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'
RUNTIMES = {
    'stage11924_transition_listwise_head_only': ART / 'stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json',
    'stage12083_next_action_repair_training': ART / 'stage12083_next_action_repair_training_probe/runtime_model/runtime_model_bundle.json',
    'stage12096_candidate_head_only_candidate_selection': ART / 'stage12096_candidate_head_only_candidate_selection_probe/runtime_model/runtime_model_bundle.json',
}
PROTECTED_ROWSETS = {
    'residual_bank': ART / 'stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl',
    'filtered_strict': ART / 'stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl',
    'old_canary_strict': ART / 'stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl',
    'filtered_validation': ART / 'stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl',
    'old_canary_validation': ART / 'stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl',
    'verifier_grounded_source_heldout_smoke': ART / 'stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_successor_rows.jsonl',
}
SCORERS = {
    'semantic_candidate_head': 'encoder_option_retrieval_semantic_candidate_head',
    'transition_candidate_head': 'encoder_option_retrieval_transition_candidate_head',
    'semantic_plus_transition_candidate_head': 'encoder_option_retrieval_semantic_plus_transition_candidate_head',
}
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


def task_type(row: dict[str, Any]) -> str:
    value = row.get('task_type')
    if value:
        return str(value)
    rid = str(row.get('row_id') or '')
    for suffix in ('next_action', 'candidate_selection', 'verifier_transition', 'continue_or_stop'):
        if rid.endswith('::' + suffix) or ('::' + suffix + '::') in rid:
            return 'transition_' + suffix
    return 'unknown'


def grouped(card: dict[str, Any]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in card.get('row_cards') or []:
        buckets.setdefault(task_type(row), []).append(row)
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
    transition_rows = [normalize_row(row) for row in read_jsonl(TRANSITION_ROWS)]
    protected = {name: [normalize_row(row) for row in read_jsonl(path)] for name, path in PROTECTED_ROWSETS.items()}
    results: dict[str, Any] = {}
    init_cards: dict[str, Any] = {}
    raw_cards: dict[str, dict[str, Any]] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime_path)
        init_cards[runtime_name] = init_card
        runtime_results: dict[str, Any] = {}
        raw_cards[runtime_name] = {}
        for scorer_name, scorer in SCORERS.items():
            card = _write_bounded_choice_eval_audit(
                OUT / runtime_name,
                model=model,
                rows=transition_rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=16,
                split_name=f'transition_projection__{scorer_name}',
                bounded_choice_aux_source=scorer,
                eval_batch_size=8,
            )
            raw_cards[runtime_name][scorer_name] = card
            runtime_results[f'transition::{scorer_name}'] = metric(card)
            runtime_results[f'transition_by_task::{scorer_name}'] = grouped(card)
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

    base_semantic = results['stage11924_transition_listwise_head_only']['transition::semantic_candidate_head']
    base_tasks = results['stage11924_transition_listwise_head_only']['transition_by_task::semantic_candidate_head']
    stage12096_transition = results['stage12096_candidate_head_only_candidate_selection']
    pure_tasks = stage12096_transition['transition_by_task::transition_candidate_head']
    composite_tasks = stage12096_transition['transition_by_task::semantic_plus_transition_candidate_head']
    pure_total = stage12096_transition['transition::transition_candidate_head']
    composite_total = stage12096_transition['transition::semantic_plus_transition_candidate_head']
    protected = stage12096_transition
    gates = {
        'pure_candidate_head_candidate_selection_ge_89': pure_tasks['transition_candidate_selection']['correct'] >= 89,
        'pure_candidate_head_next_action_ge_51': pure_tasks['transition_next_action']['correct'] >= 51,
        'pure_candidate_head_old_transition_ge_364': (pure_total.get('correct') or 0) >= 364,
        'composite_candidate_selection_ge_89': composite_tasks['transition_candidate_selection']['correct'] >= 89,
        'composite_next_action_ge_51': composite_tasks['transition_next_action']['correct'] >= 51,
        'composite_old_transition_gt_364': (composite_total.get('correct') or 0) > 364,
        'filtered_strict_preserved': protected['protected::filtered_strict'].get('correct') == 22,
        'old_canary_strict_preserved': protected['protected::old_canary_strict'].get('correct') == 23,
        'filtered_validation_preserved': (protected['protected::filtered_validation'].get('correct') or 0) >= 20,
        'old_canary_validation_preserved': (protected['protected::old_canary_validation'].get('correct') or 0) >= 21,
        'residual_preserved': (protected['protected::residual_bank'].get('correct') or 0) >= 7,
        'smoke_preserved': (protected['protected::verifier_grounded_source_heldout_smoke'].get('correct') or 0) >= 6,
    }
    protected_preserved = all(gates[name] for name in (
        'filtered_strict_preserved',
        'old_canary_strict_preserved',
        'filtered_validation_preserved',
        'old_canary_validation_preserved',
        'residual_preserved',
        'smoke_preserved',
    ))
    if protected_preserved and gates['composite_old_transition_gt_364'] and gates['composite_candidate_selection_ge_89'] and gates['composite_next_action_ge_51']:
        decision = 'stage12096_composite_transition_frontier_candidate'
    elif protected_preserved and gates['pure_candidate_head_candidate_selection_ge_89']:
        decision = 'stage12096_candidate_head_diagnostic_candidate_selection_recovered'
    else:
        decision = 'reject_stage12096_keep_stage11924_selected_transition_frontier'
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now(),
        'decision': decision,
        'device': str(DEVICE),
        'selected_transition_frontier_remains': {
            'stage': 'stage11924_transition_listwise_head_only_probe',
            'scorer': 'encoder_option_retrieval_semantic_candidate_head',
            'score': base_semantic,
            'by_task': base_tasks,
        },
        'gates': gates,
        'results': results,
        'changes_vs_stage11924_semantic': {
            'pure_transition_candidate_head': changed_rows(
                raw_cards['stage11924_transition_listwise_head_only']['semantic_candidate_head'],
                raw_cards['stage12096_candidate_head_only_candidate_selection']['transition_candidate_head'],
            ),
            'semantic_plus_transition_candidate_head': changed_rows(
                raw_cards['stage11924_transition_listwise_head_only']['semantic_candidate_head'],
                raw_cards['stage12096_candidate_head_only_candidate_selection']['semantic_plus_transition_candidate_head'],
            ),
        },
        'runtime_initialization': init_cards,
        'source_artifacts': {
            'transition_rows': rel(TRANSITION_ROWS),
            'runtimes': {name: rel(path) for name, path in RUNTIMES.items()},
            'protected_rowsets': {name: rel(path) for name, path in PROTECTED_ROWSETS.items()},
            'stage12095_request': 'runs/summaries/stage12095_candidate_head_only_candidate_selection_request.json',
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': f'runs/summaries/{NAME}.json',
            'audit_dir': rel(OUT),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f'{NAME}.json')
    print(json.dumps({
        'decision': decision,
        'gates': gates,
        'stage11924_semantic': base_semantic,
        'stage11924_by_task': base_tasks,
        'stage12096_pure_transition_candidate': pure_total,
        'stage12096_pure_by_task': pure_tasks,
        'stage12096_composite': composite_total,
        'stage12096_composite_by_task': composite_tasks,
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
