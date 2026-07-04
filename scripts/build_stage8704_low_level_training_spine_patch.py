#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8704
NAME = 'stage8704_v27_low_level_training_mechanics_spine_patch'
SUMMARY_IN = ROOT / 'runs/summaries/stage8703_low_level_training_concept_session_grep.json'
SPINE = ROOT / 'docs/MODEL_STACK_SPINE.md'
SUMMARY = ROOT / 'runs/summaries/stage8704_low_level_training_mechanics_spine_patch.json'
OUT_DIR = ROOT / f'runs/local/artifacts/{NAME}'
DOC = ROOT / 'docs/LOW_LEVEL_TRAINING_MECHANICS_SPINE_PATCH_STAGE8704.md'
REGISTRY = ROOT / 'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED = {'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'denoise_ce_training_authorized_next': False, 'runtime_authorized': False, 'source_body_authorized': False, 'gemma_authorized': False, 'promotion_ready': False}
REQUIRED_PHRASES = ['Tensor shape / dtype / device', 'MatMul / dot product / linear projection', 'Autograd / backward / gradients', 'Optimizer / scheduler', 'Current Low-Level Gaps']


def write_registry(card: dict[str, Any]) -> None:
    registry = json.loads(REGISTRY.read_text(encoding='utf-8')) if REGISTRY.exists() else {'stages': []}
    stages = [row for row in registry.get('stages', []) if row.get('stage') != STAGE]
    stages.append({'stage': STAGE, 'name': NAME, 'summary_path': str(SUMMARY), 'artifact_dir': str(OUT_DIR), 'passed': card['passed'], 'authority_rows': card['metrics']['authority_rows'], 'created_at': card['created_at_utc']})
    registry['stages'] = sorted(stages, key=lambda row: int(row.get('stage', -1)))
    registry['latest_stage'] = STAGE
    registry['latest_name'] = NAME
    registry['latest_summary_path'] = str(SUMMARY)
    registry['updated_at'] = card['created_at_utc']
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    grep = json.loads(SUMMARY_IN.read_text(encoding='utf-8'))
    spine = SPINE.read_text(encoding='utf-8')
    missing = [phrase for phrase in REQUIRED_PHRASES if phrase not in spine]
    passed = not missing and grep.get('passed') is True
    card: dict[str, Any] = {
        'stage': STAGE,
        'stage_name': NAME,
        'passed': passed,
        'authority': AUTHORITY_CLOSED,
        'source_stage': str(SUMMARY_IN.relative_to(ROOT)),
        'patched_spine': str(SPINE.relative_to(ROOT)),
        'missing_required_phrases': missing,
        'documented_not_executable_groups': grep.get('documented_not_executable_groups', []),
        'missing_index_groups': grep.get('missing_index_groups', []),
        'metrics': {'authority_rows': 0, 'required_phrases': len(REQUIRED_PHRASES), 'missing_required_phrases': len(missing), 'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'runtime_authorized': False, 'promotion_ready': False},
        'decision': 'Low-level training mechanics are now explicitly indexed in MODEL_STACK_SPINE.md.' if passed else 'Low-level training mechanics spine patch incomplete.',
        'next_best_step': 'Attach low-level mechanics to central graph, then recover runtime verifier loop or state-space compressor.',
        'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    (OUT_DIR / 'low_level_training_mechanics_spine_patch_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text(f"""# Stage {STAGE}: Low-Level Training Mechanics Spine Patch\n\nPassed: `{passed}`\n\nPatched: `{SPINE.relative_to(ROOT)}`\n\nDocumented-not-executable from Stage8703:\n\n""" + ''.join(f"- `{item}`\n" for item in grep.get('documented_not_executable_groups', [])) + "\nAll authority remains closed.\n", encoding='utf-8')
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
