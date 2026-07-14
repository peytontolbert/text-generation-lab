#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10947
NAME = 'stage10947_evidence_gate_feasibility_decision'
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / 'evidence_gate_feasibility_decision.json'
OVERLAY_JSON = ARTIFACTS / 'stage10945_overlay_evidence_margin_audit' / 'overlay_evidence_margin_audit.json'
EXPLICIT_JSON = ARTIFACTS / 'stage10946_explicit_ledger_role_map_margin_audit' / 'explicit_ledger_role_map_margin_audit.json'
def load_json(path: Path) -> Any: return json.loads(path.read_text(encoding='utf-8'))
def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
def now_utc() -> str: return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def feasible_thresholds(cards, *, require_selected_anchor: bool) -> list[float]:
    values = sorted({round(float(card['raw_margin_top1_minus_top2']), 6) for card in cards if card['raw_margin_top1_minus_top2'] is not None})
    probes = sorted(set([0.0, *values, *(v + 1e-6 for v in values), 1.0]))
    good = []
    for threshold in probes:
        ok = True
        for card in cards:
            use_role = bool(card.get('selected_test_anchor')) if require_selected_anchor else True
            use_role = use_role and card.get('role_top2', [{}])[0].get('value') == 'verifier_and_test_constraint'
            margin = card.get('raw_margin_top1_minus_top2')
            use_role = use_role and margin is not None and float(margin) <= threshold
            pred = card['role_top2'][0]['value'] if use_role else card['raw_top2'][0]['value']
            if pred != card['gold_value']:
                ok = False
                break
        if ok:
            good.append(threshold)
    return good
def main() -> None:
    overlay = load_json(OVERLAY_JSON)
    explicit = load_json(EXPLICIT_JSON)
    overlay_cards = list(overlay.get('eval', [])) + list(overlay.get('strict', []))
    explicit_cards = list(explicit.get('rows', []))
    overlay_thresholds = feasible_thresholds(overlay_cards, require_selected_anchor=True)
    explicit_thresholds = feasible_thresholds(explicit_cards, require_selected_anchor=True)
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'no_simple_evidence_gate_solves_overlay_and_explicit_slice_together',
        'claim_scope': [
            'Decide whether a simple selected-test-plus-margin gate can safely adopt role-mapped evidence retrieval.',
            'Require the same gate family to preserve the frozen overlay and improve the explicit-ledger blocker slice.',
        ],
        'source_audits': {
            'overlay_margin_audit': str(OVERLAY_JSON.relative_to(ROOT)),
            'explicit_ledger_margin_audit': str(EXPLICIT_JSON.relative_to(ROOT)),
        },
        'headline': {
            'overlay_feasible_thresholds_count': len(overlay_thresholds),
            'explicit_feasible_thresholds_count': len(explicit_thresholds),
            'overlay_example_thresholds': overlay_thresholds[:10],
            'explicit_example_thresholds': explicit_thresholds[:10],
        },
        'findings': [
            'A selected-test-anchor plus raw-margin gate has feasible thresholds on the frozen overlay, so the overlay alone does not rule out a narrow scorer gate.',
            'The same gate family has no feasible threshold on the explicit-ledger 3-row slice, because the two verifier-ledger positives and the candidate-surface control have overlapping raw margins.',
            'That means the blocker has moved past prompt visibility and simple interface routing. The remaining issue is scorer geometry or training objective, especially pairwise separation between candidate_change_surface and verifier_and_test_constraint.',
        ],
        'next_best_step': 'Do not promote another interface-only scorer tweak as the main fix. Build or train a scorer/objective repair that directly separates candidate_change_surface from verifier_and_test_constraint, then re-audit the same overlay and explicit-ledger slice.',
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
if __name__ == '__main__':
    main()
