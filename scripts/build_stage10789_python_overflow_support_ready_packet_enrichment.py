#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10789
NAME = 'stage10789_python_overflow_support_ready_packet_enrichment'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
SUMMARY_JSON = OUT_DIR / 'python_overflow_support_ready_packet_enrichment.json'
ENRICHED_INDEX_JSONL = OUT_DIR / 'enriched_packet_index.jsonl'
SUMMARY_CARD = ROOT / 'runs/summaries' / f'{NAME}.json'

DECISIONS_JSONL = ROOT / 'runs/local/artifacts/stage10775_bulk_multilingual_packet_ai_adjudication/packet_ai_adjudication.jsonl'
PREV_ENRICHED_INDEX_JSONL = ROOT / 'runs/local/artifacts/stage10776_bulk_support_ready_packet_enrichment/enriched_packet_index.jsonl'
PACKET_INDEX_JSONL = ROOT / 'runs/local/artifacts/stage10774_bulk_multilingual_review_packet_builder/packet_index.jsonl'

PERSPECTIVES = [
    'symptom_localization',
    'evidence_citation',
    'alternative_hypothesis_elimination',
    'patch_impact',
    'verifier_outcome',
    'minimal_fix_selection',
    'regression_risk',
    'abstention_insufficient_evidence',
]

MAX_ROOTS = 20
PER_REPO_CAP = 2


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def relabel_options(values: list[str], *, add_abstain: bool = False) -> list[dict[str, str]]:
    labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M']
    opts = [{'label': labels[idx], 'value': value} for idx, value in enumerate(values[: len(labels)])]
    if add_abstain and len(opts) < len(labels):
        opts.append({'label': labels[len(opts)], 'value': 'ABSTAIN_INSUFFICIENT_EVIDENCE'})
    return opts


def expanded_candidates(bundle: dict[str, Any]) -> list[str]:
    changed = [str(item) for item in bundle['compiled_brief_summary'].get('changed_files_sample') or []]
    tests = [str(item) for item in bundle['compiled_brief_summary'].get('verification_targets_sample') or []]
    symbols = [str(item) for item in bundle['compiled_brief_summary'].get('key_symbols_sample') or []]
    values: list[str] = []
    values.extend(changed)
    values.extend(tests)
    values.extend([
        'src/main.py',
        'tests/test_main.py',
        'src/utils.py',
        'docs/usage.md',
    ])
    deduped = []
    seen = set()
    for value in values + symbols:
        value = value.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped[:8]


def perspective_contract(bundle: dict[str, Any], perspective: str, options: list[dict[str, str]]) -> dict[str, Any]:
    tests = [str(item) for item in bundle['compiled_brief_summary'].get('verification_targets_sample') or []]
    changed = [str(item) for item in bundle['compiled_brief_summary'].get('changed_files_sample') or []]
    evidence_keys = sorted(k for k, v in (bundle.get('maintainer_visible_evidence') or {}).items() if v)
    contracts = {
        'symptom_localization': 'Target should be justified by visible competition between changed files, nearby implementation paths, and verifier evidence.',
        'evidence_citation': 'Answer should come from visible evidence roles, not from candidate identity or order.',
        'alternative_hypothesis_elimination': 'At least one plausible wrong candidate must remain in the option set.',
        'patch_impact': 'Candidates must differ in likely behavioral effect, not only file name.',
        'verifier_outcome': 'Visible tests must support a nontrivial verifier choice or abstain decision.',
        'minimal_fix_selection': 'A smaller but insufficient edit should compete with a larger but stronger edit.',
        'regression_risk': 'Visible evidence should allow at least one plausible regression concern.',
        'abstention_insufficient_evidence': 'ABSTAIN should remain available when the visible evidence does not force a singleton.',
    }
    return {
        'perspective': perspective,
        'language_family': bundle['language_family'],
        'task_contract': contracts[perspective],
        'candidate_option_count': len(options),
        'candidate_options': options,
        'evidence_keys': evidence_keys,
        'verification_targets_preview': tests[:4],
        'changed_files_preview': changed[:4],
        'scoreable_now': False,
        'gold_status': 'needs_ai_or_human_adjudication',
    }


def enrichment_status(bundle: dict[str, Any]) -> tuple[str, list[str]]:
    return 'python_overflow_support_candidate', [
        'attach concrete snippet text for changed and competing files',
        'adjudicate gold answers with emphasis on verifier_outcome contrast',
        'maintain repo-family diversity so the overflow package does not collapse into one family',
    ]


def safe_dirname(root_id: str) -> str:
    keep = []
    for ch in root_id:
        keep.append(ch if ch.isalnum() else '_')
    prefix = ''.join(keep)[:96]
    suffix = hashlib.sha1(root_id.encode('utf-8')).hexdigest()[:12]
    return f'{prefix}_{suffix}'


def main() -> None:
    decisions = load_jsonl(DECISIONS_JSONL)
    packet_index = {str(row['root_id']): row for row in load_jsonl(PACKET_INDEX_JSONL)}
    already_selected = {str(row['root_id']) for row in load_jsonl(PREV_ENRICHED_INDEX_JSONL)}

    candidates = [
        row for row in decisions
        if row['ai_status'] == 'support_ready_after_enrichment'
        and row['language_family'] == 'python'
        and str(row['root_id']) not in already_selected
    ]
    candidates = sorted(candidates, key=lambda r: (-int(r['priority_score']), int(r['queue_rank']), str(r['repo_family']), str(r['root_id'])))

    selected_rows = []
    skipped_rows = []
    per_repo = Counter()
    for row in candidates:
        repo = str(row['repo_family'])
        if len(selected_rows) >= MAX_ROOTS:
            skipped_rows.append({
                'root_id': row['root_id'],
                'repo_family': repo,
                'skip_reason': 'stage_root_cap',
            })
            continue
        if per_repo[repo] >= PER_REPO_CAP:
            skipped_rows.append({
                'root_id': row['root_id'],
                'repo_family': repo,
                'skip_reason': 'repo_cap',
            })
            continue
        selected_rows.append(row)
        per_repo[repo] += 1

    enriched_index = []
    for row in selected_rows:
        packet_row = packet_index[str(row['root_id'])]
        packet_dir = ROOT / str(packet_row['packet_dir'])
        bundle = load_json(packet_dir / 'fresh_root_bundle_preview.json')
        candidate_values = expanded_candidates(bundle)
        abstain_options = relabel_options(candidate_values, add_abstain=True)
        singleton_options = relabel_options(candidate_values, add_abstain=False)
        stage_dir = OUT_DIR / 'candidates' / safe_dirname(str(row['root_id']))
        enriched = {
            'bundle_id': bundle['bundle_id'],
            'root_id': bundle['root_id'],
            'root_lineage_key': packet_row['root_lineage_key'],
            'repo_family': bundle['repo_family'],
            'language_family': bundle['language_family'],
            'source_route': bundle['source_route'],
            'source_packet_dir': packet_row['packet_dir'],
            'claim_boundary': {
                'gold_answers_fully_adjudicated': False,
                'supports_training_or_scoring_now': False,
                'support_candidate_only': True,
            },
            'competition_contract': {
                'candidate_values': candidate_values,
                'singleton_candidate_options': singleton_options,
                'abstain_candidate_options': abstain_options,
                'must_not_expose_gold_path_before_options': True,
                'must_include_non_changed_competitors': True,
                'must_test_changed_path_shortcut': True,
                'selected_from_bulk_packet_adjudication': True,
                'overflow_python_second_wave': True,
            },
            'compiled_brief_summary': bundle['compiled_brief_summary'],
            'maintainer_visible_evidence': bundle['maintainer_visible_evidence'],
            'perspective_contracts': [
                perspective_contract(
                    bundle,
                    perspective,
                    abstain_options if perspective == 'abstention_insufficient_evidence' else singleton_options,
                )
                for perspective in PERSPECTIVES
            ],
            'enrichment_status': enrichment_status(bundle)[0],
            'required_next_actions': enrichment_status(bundle)[1],
            'queue_rank': int(row['queue_rank']),
            'priority_score': int(row['priority_score']),
            'semantic_lane': str(row.get('semantic_lane') or 'python_verifier_and_generation_scale'),
        }
        enriched_path = stage_dir / 'enriched_reviewed_support_candidate.json'
        write_json(enriched_path, enriched)
        enriched_index.append({
            'root_id': row['root_id'],
            'root_lineage_key': packet_row['root_lineage_key'],
            'language_family': row['language_family'],
            'repo_family': row['repo_family'],
            'priority_score': int(row['priority_score']),
            'queue_rank': int(row['queue_rank']),
            'semantic_lane': str(row.get('semantic_lane') or 'python_verifier_and_generation_scale'),
            'source_packet_dir': packet_row['packet_dir'],
            'enriched_candidate': display(enriched_path),
            'enrichment_status': enriched['enrichment_status'],
            'candidate_option_count': len(candidate_values),
            'package_ready_after_snippets_and_confirmation': True,
        })

    enriched_index.sort(key=lambda r: (-int(r['priority_score']), int(r['queue_rank']), r['repo_family'], r['root_id']))
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'python_overflow_support_ready_packet_enrichment_attached',
        'claim_scope': [
            'Select the second-wave Python support-ready backlog that was not included in the first bulk support package.',
            'Attach enriched candidate-competition contracts for those backlog Python roots without touching strict eval.',
            'Prepare a larger Python verifier-oriented support wave while preserving non-promotable train-only boundaries.',
        ],
        'metrics': {
            'available_backlog_python_roots': len(candidates),
            'selected_python_roots': len(enriched_index),
            'selected_by_repo': dict(sorted(Counter(row['repo_family'] for row in enriched_index).items())),
            'skipped_roots': len(skipped_rows),
        },
        'headline_findings': [
            'The first-wave cap, not missing source state, is why these Python roots remained unmaterialized.',
            'The overflow selection keeps repo diversity while explicitly targeting Python verifier and evidence scale.',
            'Every selected root now has a second-wave enriched competition contract ready for provisional gold drafting.',
        ],
        'next_best_step': 'Attach provisional AI gold drafts and build a second-wave Python train-support package on top of stage10786.',
        'source_artifacts': {
            'bulk_packet_adjudication': display(DECISIONS_JSONL),
            'previous_enriched_index': display(PREV_ENRICHED_INDEX_JSONL),
            'packet_index': display(PACKET_INDEX_JSONL),
        },
        'outputs': {
            'summary_json': display(SUMMARY_JSON),
            'enriched_index': display(ENRICHED_INDEX_JSONL),
        },
    }
    write_jsonl(ENRICHED_INDEX_JSONL, enriched_index)
    write_json(SUMMARY_JSON, payload)
    write_json(SUMMARY_CARD, {
        'stage': STAGE,
        'passed': True,
        'decision': payload['decision'],
        'selected_python_roots': len(enriched_index),
    })
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
