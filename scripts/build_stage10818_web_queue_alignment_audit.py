#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'

STAGE = 10818
NAME = 'stage10818_web_queue_alignment_audit'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'web_queue_alignment_audit.json'
STATUS_JSONL = OUT_DIR / 'web_root_status_manifest.jsonl'

CURRENT_ROOTS = ARTIFACTS / 'stage10814_reviewed_v27_plus_cpp_python_queue_support_package' / 'reviewed_v27_plus_cpp_python_queue_root_manifest.jsonl'
WEB_SUPPLY_AUDIT = ARTIFACTS / 'stage10175_web_root_supply_and_bundle_gap_audit' / 'web_root_supply_and_bundle_gap_audit.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def classify(row: dict[str, Any]) -> dict[str, Any]:
    base = {
        'root_id': row.get('root_id'),
        'bundle_id': row.get('bundle_id'),
        'record_type': row.get('record_type'),
        'repo_id': row.get('repo_id'),
        'repo_family': row.get('repo_family'),
        'split': row.get('split'),
        'split_role': row.get('split_role'),
        'selected_test_anchor': bool(row.get('selected_test_anchor')),
        'verifier_anchor': bool(row.get('verifier_anchor')),
        'strict_eval_eligible': bool(row.get('strict_eval_eligible')),
        'stress_overlap_only': bool(row.get('stress_overlap_only')),
        'same_surface_eval_admissible': bool(row.get('same_surface_eval_admissible')),
        'claim_notes': list(row.get('claim_notes') or []),
    }

    notes = set(str(v) for v in (row.get('claim_notes') or []))
    if row.get('repo_id') == 'bddy_website' and not row.get('selected_test_anchor'):
        base.update({
            'status': 'pure_web_unanchored_reviewed_root',
            'next_action': 'Recover selected-test or verifier anchors before treating pure-web rows as strong support for broader web claims.',
        })
        return base

    if row.get('stress_overlap_only') and row.get('repo_id') == 'code_assist':
        base.update({
            'status': 'mixed_language_web_stress_only',
            'next_action': 'Keep as overlap/stress coverage only; do not promote as pure-web headline evidence.',
        })
        return base

    if row.get('record_type') == 'adjudicated_successor_row':
        base.update({
            'status': 'successor_row_stress_only',
            'next_action': 'Keep as auxiliary stress/support evidence only; it is not a full reviewed web bundle.',
        })
        return base

    base.update({
        'status': 'other_web_root',
        'next_action': 'Inspect manually if this root is intended for a promotable path.',
    })
    return base


def main() -> None:
    root_rows = [row for row in load_jsonl(CURRENT_ROOTS) if str(row.get('language_family') or '') == 'web_js_ts_html']
    status_rows = [classify(row) for row in root_rows]
    write_jsonl(STATUS_JSONL, status_rows)

    status_counts = Counter(str(row['status']) for row in status_rows)
    supply_audit = load_json(WEB_SUPPLY_AUDIT)

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'passed': True,
        'decision': 'web_root_inventory_split_between_unanchored_pure_web_and_stress_only_anchored_web',
        'claim_scope': [
            'Reconcile the current web roots in the multilingual v2.7 support package with the earlier web supply audit.',
            'Separate pure-web reviewed roots from mixed-language or successor-row stress roots so future web work targets the real missing anchor problem.',
        ],
        'headline_findings': [
            'The current package contains two reviewed pure-web roots, both from bddy_website, but neither has a selected-test or verifier anchor.',
            'The only anchored web evidence in the current package is code_assist, and both of those web entries are stress-only rather than promotable pure-web support.',
            'So the real web frontier is not more web rows; it is at least one pure-web reviewed root with an honest verifier/test anchor.',
        ],
        'metrics': {
            'web_root_count': len(status_rows),
            'status_counts': dict(sorted(status_counts.items())),
            'pure_web_unanchored_count': sum(1 for row in status_rows if row['status'] == 'pure_web_unanchored_reviewed_root'),
            'anchored_web_stress_only_count': sum(1 for row in status_rows if row['status'] == 'mixed_language_web_stress_only'),
            'successor_row_stress_only_count': sum(1 for row in status_rows if row['status'] == 'successor_row_stress_only'),
            'bddy_distinct_bundle_digests': int((supply_audit.get('inventory_web_summary') or {}).get('distinct_bundle_digests') or 0),
        },
        'source_artifacts': {
            'current_root_manifest': rel(CURRENT_ROOTS),
            'web_supply_audit': rel(WEB_SUPPLY_AUDIT),
        },
        'next_best_steps': [
            'Do not treat the code_assist web root as the solution to the web language lane; it remains overlap/stress only.',
            'Recover or build at least one pure-web reviewed root with a real selected test or verifier anchor.',
            'Until then, keep the current pure-web roots useful for realism and bundle diversity, but headline web claims should remain conservative.',
        ],
        'outputs': {
            'summary_json': rel(SUMMARY_JSON),
            'status_manifest_jsonl': rel(STATUS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
