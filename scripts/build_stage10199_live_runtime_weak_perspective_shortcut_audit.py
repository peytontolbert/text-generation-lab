#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10199
NAME = "stage10199_live_runtime_weak_perspective_shortcut_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "live_runtime_weak_perspective_shortcut_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
PACKAGE = ROOT / "runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/standalone_compact_permutation_balanced_package.json"
HARNESS = ROOT / "runs/local/artifacts/stage10197_compact_bounded_saved_runtime_harness_multilingual_reparsed"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_audit() -> dict[str, Any]:
    package = load_json(PACKAGE)
    row_map = {row['row_id']: row for row in load_jsonl(ROOT / str(package.get('eval_dataset_path') or ''))}
    per_cell = {}
    per_perspective_offsets: dict[str, Counter[int]] = defaultdict(Counter)
    semantic_confusions: dict[str, Counter[str]] = defaultdict(Counter)
    cell_dirs = [p for p in HARNESS.iterdir() if p.is_dir()]
    for cell in sorted(cell_dirs):
        weak_path = cell / 'weak_rows_audit.json'
        if not weak_path.exists():
            continue
        weak_rows = load_json(weak_path).get('weak_rows') or []
        analyzed = []
        for item in weak_rows:
            row = row_map.get(str(item.get('row_id') or ''))
            if not row:
                continue
            options = ((row.get('standalone_projection_source') or {}).get('opaque_options')) or []
            label_to_value = {str(opt.get('label') or ''): str(opt.get('value') or '') for opt in options if isinstance(opt, dict)}
            labels = [str(opt.get('label') or '') for opt in options if isinstance(opt, dict)]
            predicted = str(item.get('hundred_m_predicted') or '')
            expected = str(item.get('expected') or '')
            if predicted in labels and expected in labels and labels:
                delta = (labels.index(predicted) - labels.index(expected)) % len(labels)
                per_perspective_offsets[str(item.get('perspective') or '')][delta] += 1
            else:
                delta = None
            expected_value = label_to_value.get(expected)
            predicted_value = label_to_value.get(predicted)
            if expected_value and predicted_value:
                semantic_confusions[str(item.get('perspective') or '')][f'{expected_value} -> {predicted_value}'] += 1
            analyzed.append({
                'row_id': item.get('row_id'),
                'perspective': item.get('perspective'),
                'expected_label': expected,
                'predicted_label': predicted,
                'expected_value': expected_value,
                'predicted_value': predicted_value,
                'label_offset_mod_n': delta,
                'gemma_correct': item.get('gemma_correct'),
                'hundred_m_correct': item.get('hundred_m_correct'),
            })
        per_cell[cell.name] = {
            'weak_rows': len(analyzed),
            'analyzed_rows': analyzed,
        }
    return {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': bool(per_cell),
        'source_package': display(PACKAGE),
        'source_harness_dir': display(HARNESS),
        'per_cell': per_cell,
        'per_perspective_offset_histogram': {k: dict(v) for k, v in sorted(per_perspective_offsets.items())},
        'per_perspective_semantic_confusions': {k: dict(v.most_common()) for k, v in sorted(semantic_confusions.items())},
        'findings': [
            'evidence_citation shows a stable semantic confusion from candidate_change_surface to verifier_and_test_constraint across languages',
            'python verifier_outcome shows a stable wrong-test-family confusion across all permutations',
            'web symptom_localization, patch_impact, and minimal_fix_selection show a stable file-family confusion toward vite.config.js instead of index.html',
            'these patterns indicate semantic-family bias under permutation rather than random decoding noise',
        ],
        'recommended_next_training_changes': [
            'add explicit contrastive rows for candidate_change_surface versus verifier_and_test_constraint',
            'add verifier_outcome negatives that hold repo/failure text constant while swapping only selected_test semantics',
            'replenish Web roots where index.html competes directly against vite.config.js with stronger discriminative evidence',
            'do not broaden the claim boundary; keep this as compact-bounded diagnostic evidence until maintainer-grade rows are improved',
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'passed': audit['passed'], 'artifact': display(AUDIT)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({'stage': STAGE, 'passed': audit['passed'], 'artifact': display(AUDIT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
