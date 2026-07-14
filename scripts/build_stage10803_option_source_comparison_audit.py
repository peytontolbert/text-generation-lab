#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

STAGE = 10803
NAME = 'stage10803_option_source_comparison_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
OUT_JSON = OUT_DIR / 'stage10803_option_source_comparison_audit.json'
RUNTIME_BUNDLE = ROOT / 'runs/local/artifacts/stage10802_python_plus_rust_competition_support_probe/runtime_model/runtime_model_bundle.json'
MANIFEST = ROOT / 'runs/local/artifacts/stage10801_python_plus_rust_competition_support_probe_request/python_plus_rust_competition_support_probe_manifest.jsonl'
SOURCES = [
    'decoder_first_step',
    'encoder_pooled',
    'encoder_option_retrieval',
    'encoder_option_retrieval_conditioned',
]
FOCUS_IDS = {
    'stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact',
    'stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact',
}


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    strict_rows = [row for row in load_jsonl(MANIFEST) if row.get('split') == 'strict_eval']
    bundle = json.loads(RUNTIME_BUNDLE.read_text(encoding='utf-8'))
    metadata = bundle['metadata']
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(json.loads(Path(str(metadata['model_config'])).read_text(encoding='utf-8')))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata['tokenizer_json'])), Path(str(metadata['tokenizer_config'])))

    summary = []
    focus: dict[str, list[dict[str, object]]] = {}
    for source in SOURCES:
        card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=strict_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f'strict_eval_{source}',
            bounded_choice_aux_source=source,
            eval_batch_size=8,
        )
        summary.append({
            'source': source,
            'constrained_choice_top1_accuracy': card.get('constrained_choice_top1_accuracy'),
            'full_vocab_top1_accuracy': card.get('full_vocab_top1_accuracy'),
            'rows_with_target_rank_1': card.get('rows_with_target_rank_1'),
        })
        focus[source] = [row for row in (card.get('row_cards') or []) if row.get('row_id') in FOCUS_IDS]

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'runtime_bundle': str(RUNTIME_BUNDLE.relative_to(ROOT)),
        'manifest': str(MANIFEST.relative_to(ROOT)),
        'strict_rows': len(strict_rows),
        'summary': summary,
        'focus': focus,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
