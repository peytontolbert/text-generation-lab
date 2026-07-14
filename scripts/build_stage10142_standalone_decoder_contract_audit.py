#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10142
NAME = 'stage10142_standalone_decoder_contract_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
OUT_PATH = OUT_DIR / 'standalone_decoder_contract_audit.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'
PREDICTIONS_ROOT = ROOT / 'runs/local/artifacts/stage10140_first_wave_bundle_inference'
PAYLOAD = ROOT / 'runs/local/artifacts/stage10141_standalone_bounded_bundle_projection/standalone_bounded_bundle_projection.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def stable_hash(value: str) -> str:
    import hashlib, json
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode('utf-8')).hexdigest()


def safe_cell_dir_name(cell_key: str) -> str:
    normalized = cell_key.replace('::', '__')
    if len(normalized) <= 120:
        return normalized
    return normalized[:96] + '__' + stable_hash(cell_key)[:16]


def run_dir(cell_key: str) -> Path:
    return PREDICTIONS_ROOT / safe_cell_dir_name(cell_key)


def audit_run(run: dict[str, Any]) -> dict[str, Any]:
    cell_key = str(run.get('cell_key') or '')
    task_rows = [row for row in ((run.get('task_pack') or {}).get('rows') or []) if isinstance(row, dict)]
    predictions_path = run_dir(cell_key) / 'bundle_predictions.json'
    bundle_predictions = load_json(predictions_path)
    predicted_rows = [row for row in bundle_predictions.get('hundred_m') or [] if isinstance(row, dict)]
    row_index = {str(row.get('row_id') or ''): row for row in task_rows}
    unique_predictions = Counter()
    conformance_failures = []
    answer_kind_counts = Counter()
    language = str((run.get('task_pack') or {}).get('language_family') or '')
    correct = 0
    conforming = 0
    for pred in predicted_rows:
        row_id = str(pred.get('row_id') or '')
        compiled = row_index.get(row_id, {})
        answer_kind = str(compiled.get('expected_answer_kind') or pred.get('answer_kind') or '')
        answer_kind_counts[answer_kind] += 1
        predicted_text = str(pred.get('predicted') or '')
        unique_predictions[predicted_text] += 1
        if pred.get('correct') is True:
            correct += 1
        options = compiled.get('opaque_options') if isinstance(compiled.get('opaque_options'), list) else []
        allowed_labels = {str(item.get('label')) for item in options if isinstance(item, dict) and item.get('label')}
        is_conforming = predicted_text in allowed_labels if answer_kind == 'opaque_choice' else False
        if is_conforming:
            conforming += 1
        else:
            conformance_failures.append({
                'row_id': row_id,
                'perspective': compiled.get('perspective'),
                'predicted': predicted_text,
                'allowed_labels': sorted(allowed_labels),
            })
    rows = len(predicted_rows)
    top_prediction, top_prediction_count = ('', 0)
    if unique_predictions:
        top_prediction, top_prediction_count = unique_predictions.most_common(1)[0]
    return {
        'cell_key': cell_key,
        'language_family': language,
        'rows': rows,
        'correct': correct,
        'accuracy': (correct / rows) if rows else None,
        'conforming_rows': conforming,
        'conformance_rate': (conforming / rows) if rows else None,
        'unique_prediction_count': len(unique_predictions),
        'top_prediction': top_prediction,
        'top_prediction_count': top_prediction_count,
        'top_prediction_rate': (top_prediction_count / rows) if rows else None,
        'answer_kind_counts': dict(answer_kind_counts),
        'conformance_failures': conformance_failures[:8],
        'predictions_path': display(predictions_path),
    }


def build_audit() -> dict[str, Any]:
    payload = load_json(PAYLOAD)
    runs = [row for row in payload.get('runs') or [] if isinstance(row, dict)]
    audits = [audit_run(run) for run in runs if run_dir(str(run.get('cell_key') or '')).exists()]
    by_language = defaultdict(list)
    for audit in audits:
        by_language[str(audit.get('language_family') or '')].append(audit)
    macro_accuracy = sum(float(a.get('accuracy') or 0.0) for a in audits) / len(audits) if audits else None
    macro_conformance = sum(float(a.get('conformance_rate') or 0.0) for a in audits) / len(audits) if audits else None
    collapse_cells = [a['cell_key'] for a in audits if (a.get('top_prediction_rate') or 0.0) >= 0.5]
    blocked = bool(audits) and (macro_conformance == 0.0 or len(collapse_cells) == len(audits))
    return {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'source_payload': display(PAYLOAD),
        'predictions_root': display(PREDICTIONS_ROOT),
        'passed': True,
        'metrics': {
            'audited_runs': len(audits),
            'macro_accuracy': macro_accuracy,
            'macro_conformance_rate': macro_conformance,
            'collapse_cells': len(collapse_cells),
        },
        'eval_hardening': {
            'standalone_score_claim_allowed': not blocked,
            'blocked_reason': 'decoder_contract_mismatch_or_output_collapse' if blocked else None,
            'requirements_for_honest_claim': [
                'nonzero option-label conformance on bounded projection',
                'no dominant canned prediction across most cells',
                'bundle-level exact accuracy above trivial collapse baseline',
            ],
        },
        'by_language': {
            language: {
                'runs': len(items),
                'macro_accuracy': sum(float(item.get('accuracy') or 0.0) for item in items) / len(items),
                'macro_conformance_rate': sum(float(item.get('conformance_rate') or 0.0) for item in items) / len(items),
            }
            for language, items in sorted(by_language.items())
        },
        'runs': audits,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    OUT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'passed': audit['passed'], 'artifact': display(OUT_PATH), 'metrics': audit['metrics'], 'standalone_score_claim_allowed': audit['eval_hardening']['standalone_score_claim_allowed']}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'stage': STAGE, 'passed': audit['passed'], 'artifact': display(OUT_PATH), 'metrics': audit['metrics'], 'standalone_score_claim_allowed': audit['eval_hardening']['standalone_score_claim_allowed']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
