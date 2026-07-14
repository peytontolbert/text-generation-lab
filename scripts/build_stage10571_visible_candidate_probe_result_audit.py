#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10571
NAME = "stage10571_visible_candidate_probe_result_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "visible_candidate_probe_result_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

S65 = ROOT / "runs/local/artifacts/stage10565_visible_candidate_decisive_evidence_support_package/visible_candidate_decisive_evidence_support_package.json"
S67 = ROOT / "runs/local/artifacts/stage10567_visible_candidate_decisive_evidence_probe/bounded_decoder_probe/execution_result.json"
S69 = ROOT / "runs/local/artifacts/stage10569_visible_candidate_decisive_evidence_canary_audit/visible_candidate_decisive_evidence_canary_audit.json"
S70 = ROOT / "runs/local/artifacts/stage10570_visible_candidate_successor_same_manifest_comparison/visible_candidate_successor_same_manifest_comparison.json"
S63 = ROOT / "runs/local/artifacts/stage10563_visible_candidate_transition_bounded_audit/visible_candidate_transition_bounded_audit.json"
S62 = ROOT / "runs/local/artifacts/stage10562_visible_candidate_successor_same_manifest_comparison/visible_candidate_successor_same_manifest_comparison.json"
S58 = ROOT / "runs/local/artifacts/stage10558_masked_projection_successor_with_v27_preservation_canary_audit/masked_projection_successor_with_v27_preservation_canary_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding='utf-8')


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def main() -> None:
    s65 = load_json(S65)
    s67 = load_json(S67)
    s69 = load_json(S69)
    s70 = load_json(S70)
    s63 = load_json(S63)
    s62 = load_json(S62)
    s58 = load_json(S58)

    current = {
        'stage10565_support_rows': ((s65.get('rows') or {}).get('emitted_rows')),
        'stage10567_strict_bounded_accuracy': (((s67.get('bounded_choice_eval') or {}).get('strict_eval')) or {}).get('constrained_choice_top1_accuracy'),
        'stage10567_strict_rows_with_target_rank_1': ((((s67.get('bounded_choice_eval') or {}).get('strict_eval')) or {}).get('rows_with_target_rank_1')),
        'stage10569_canary_bounded_accuracy': ((s69.get('summary') or {}).get('bounded_accuracy')),
        'stage10569_canary_greedy_exact_accuracy': ((s69.get('summary') or {}).get('greedy_exact_accuracy')),
        'stage10570_hundred_m_exact': ((((s70.get('hundred_m') or {}).get('overall')) or {}).get('exact_accuracy')),
        'stage10570_gemma_exact': ((((s70.get('gemma12b') or {}).get('overall')) or {}).get('exact_accuracy')),
        'stage10570_hundred_m_decisive_exact': ((((s70.get('hundred_m') or {}).get('by_target_subtype')) or {}).get('decisive_evidence_top1') or {}).get('exact_accuracy'),
        'stage10570_gemma_decisive_exact': ((((s70.get('gemma12b') or {}).get('by_target_subtype')) or {}).get('decisive_evidence_top1') or {}).get('exact_accuracy'),
    }
    baseline = {
        'stage10558_canary_bounded_accuracy': ((s58.get('summary') or {}).get('bounded_accuracy')),
        'stage10563_decoder_first_step_strict_accuracy': (((s63.get('summary') or {}).get('decoder_first_step')) or {}).get('accuracy'),
        'stage10563_decisive_decoder_accuracy': ((((s63.get('per_target_subtype') or {}).get('decisive_evidence_top1')) or {}).get('decoder_first_step') or {}).get('accuracy'),
        'stage10562_hundred_m_exact': ((((s62.get('hundred_m') or {}).get('overall')) or {}).get('exact_accuracy')),
        'stage10562_gemma_exact': ((((s62.get('gemma12b') or {}).get('overall')) or {}).get('exact_accuracy')),
        'stage10562_hundred_m_decisive_exact': ((((s62.get('hundred_m') or {}).get('by_target_subtype')) or {}).get('decisive_evidence_top1') or {}).get('exact_accuracy'),
    }
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'inputs': {
            'stage10565_support_package': display(S65),
            'stage10567_execution_result': display(S67),
            'stage10569_canary_audit': display(S69),
            'stage10570_same_manifest_comparison': display(S70),
            'stage10563_transition_baseline': display(S63),
            'stage10562_generation_baseline': display(S62),
            'stage10558_canary_baseline': display(S58),
        },
        'current_state': current,
        'baseline_state': baseline,
        'deltas': {
            'canary_bounded_delta': None if current['stage10569_canary_bounded_accuracy'] is None or baseline['stage10558_canary_bounded_accuracy'] is None else current['stage10569_canary_bounded_accuracy'] - baseline['stage10558_canary_bounded_accuracy'],
            'strict_bounded_delta_vs_stage10563': None if current['stage10567_strict_bounded_accuracy'] is None or baseline['stage10563_decoder_first_step_strict_accuracy'] is None else current['stage10567_strict_bounded_accuracy'] - baseline['stage10563_decoder_first_step_strict_accuracy'],
            'greedy_exact_delta_vs_stage10562': None if current['stage10570_hundred_m_exact'] is None or baseline['stage10562_hundred_m_exact'] is None else current['stage10570_hundred_m_exact'] - baseline['stage10562_hundred_m_exact'],
            'decisive_exact_delta_vs_stage10562': None if current['stage10570_hundred_m_decisive_exact'] is None or baseline['stage10562_hundred_m_decisive_exact'] is None else current['stage10570_hundred_m_decisive_exact'] - baseline['stage10562_hundred_m_decisive_exact'],
            'same_manifest_delta_vs_gemma': None if current['stage10570_hundred_m_exact'] is None or current['stage10570_gemma_exact'] is None else current['stage10570_hundred_m_exact'] - current['stage10570_gemma_exact'],
        },
        'truthful_read': [
            'The stage10565 support package did not regress the repaired v2.7 canary: stage10569 remains 22/24 bounded, matching stage10558.',
            'On the rebuilt 54-row strict visible-candidate slice, stage10567 improved greedy exact generation over stage10562 from 0/54 to 6/54 and now edges Gemma overall 6/54 vs 4/54.',
            'However, the bounded strict accuracy recorded inside stage10567 is only 7/54, far below the stage10563 saved-runtime baseline of 36/54. The decisive-evidence-only support helped raw label generation somewhat but damaged broader rebuilt-slice bounded behavior.',
            'This means stage10567 is diagnostic progress, not a promotable frontier upgrade.',
        ],
        'next_actions': [
            'Do not promote stage10567 as the new standalone frontier.',
            'Keep stage10569 canary and stage10570 same-manifest comparison as the honest result package for this probe.',
            'Next support package should mix decisive_evidence with a small verifier/retrieve preservation subset from the rebuilt visible-candidate contract rather than training decisive_evidence only.',
            'Rust and web root supply remain too thin for a strong multilingual repair claim; compile fresh disjoint roots before expecting broad language wins on the rebuilt successor surface.',
        ],
        'outputs': {
            'audit_json': display(OUT_JSON),
        },
    }
    write_json(OUT_JSON, payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload['deltas'], indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
