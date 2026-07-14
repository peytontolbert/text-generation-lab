#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10955
NAME = 'stage10955_evidence_scorer_blend_decision'
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / 'evidence_scorer_blend_decision.json'
BLEND_JSON = ARTIFACTS / 'stage10954_evidence_scorer_blend_audit' / 'evidence_scorer_blend_audit.json'
POSTRUN_JSON = ARTIFACTS / 'stage10953_evidence_contrast_margin_postrun_audit' / 'evidence_contrast_margin_postrun_audit.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def main() -> None:
    blend = load_json(BLEND_JSON)
    postrun = load_json(POSTRUN_JSON)
    search = blend.get('search') or {}
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'no_honest_linear_evidence_scorer_fix_remaining',
        'claim_scope': [
            'Decide whether any simple inference-side scorer calibration still remains after the direct contrastive probe failed.',
            'Use only families that preserve the frozen overlay while repairing the explicit-ledger candidate-versus-verifier slice.',
        ],
        'source_artifacts': {
            'blend_audit': str(BLEND_JSON.relative_to(ROOT)),
            'contrast_postrun': str(POSTRUN_JSON.relative_to(ROOT)),
        },
        'headline': {
            'overlay_accuracy_after_contrast_probe': ((postrun.get('overlay') or {}).get('strict_accuracy')),
            'explicit_accuracy_after_contrast_probe': (((postrun.get('explicit_ledger_slice') or {}).get('overall') or {}).get('exact_accuracy')),
            'feasible_blends': len(search.get('feasible_blends') or []),
            'feasible_biases': len(search.get('feasible_biases') or []),
            'best_blend_overlay_correct': ((search.get('best_blend') or {}).get('overlay_correct')),
            'best_blend_explicit_correct': ((search.get('best_blend') or {}).get('explicit_correct')),
            'best_bias_overlay_correct': ((search.get('best_bias') or {}).get('overlay_correct')),
            'best_bias_explicit_correct': ((search.get('best_bias') or {}).get('explicit_correct')),
        },
        'findings': [
            'The direct contrastive training probe preserved the frozen overlay but left the explicit-ledger slice at 1/3, so objective-only shaping did not move the blocker.',
            'The scorer-blend audit found zero feasible convex raw/role blends and zero feasible verifier/candidate semantic bias settings that solve the explicit slice while preserving all 46 frozen overlay rows.',
            'The best blend only reaches 2/3 on the explicit slice and regresses 3 overlay rows; the best bias family reaches 2/3 and regresses 4 overlay rows.',
            'This moves the remaining blocker out of simple scorer calibration. The next honest lever is row geometry or scorer architecture, not another weight tweak.',
        ],
        'next_root_building_targets': [
            'Fresh Python evidence-citation roots where verifier_and_test_constraint is the gold fact and candidate_change_surface is the strongest tempting negative, with non-aliased visible evidence.',
            'Fresh C/C++ evidence-citation roots with the same verifier-versus-candidate competition from disjoint repo families.',
            'At least one fresh pure-web positive-control evidence root where candidate_change_surface is genuinely correct and selected-test/verifier anchors are present, so future scorer changes can be audited honestly.',
            'A replacement Rust evidence root that is non-aliased and verifier-anchored, since the old tokenizers blocker was invalidated and cannot serve as a clean strict blocker.',
        ],
        'next_modeling_targets': [
            'If scorer work continues, it must be a richer architecture than linear calibration, such as evidence-role-specific heads or pairwise candidate-versus-verifier comparison scoring.',
            'Keep the frozen overlay as the honesty gate and stop running generic support probes until new roots or a new scorer architecture are ready.',
        ],
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
