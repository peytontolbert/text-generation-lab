#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10232
NAME = "stage10232_exact_admitted_projection_runtime_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "exact_admitted_projection_runtime_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
PAYLOAD = ROOT / "runs/local/artifacts/stage10225_adjudicated_projection_bundle_coherence_runtime_payload/adjudicated_projection_bundle_coherence_runtime_payload.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10224_bundle_coherence_counterbalance_probe/runtime_model/runtime_model_bundle.json"
RUNNER = ROOT / "scripts/run_stage10140_first_wave_bundle_inference.py"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = load_json(PAYLOAD)
    runner = load_module('stage10232_stage10140_runner', RUNNER)
    runs = [row for row in payload.get('runs') or [] if isinstance(row, dict)]
    results = []
    bundle_cards = []
    per_language_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_correct = 0
    total_rows = 0
    macro_scores = []
    backend = {
        'kind': 'preserved_bounded_choice_scoring',
        'runtime_model_bundle': str(RUNTIME_BUNDLE),
        'bounded_choice_aux_source': 'encoder_option_retrieval',
        'max_encoder_tokens': 768,
        'device': 'cuda',
    }
    for run in runs:
        task_pack = run.get('task_pack') or {}
        bundle_id = str(task_pack.get('bundle_id') or '')
        language = str(task_pack.get('language_family') or bundle_id.split('::')[-1])
        rows = [row for row in task_pack.get('rows') or [] if isinstance(row, dict)]
        scored = runner.run_rows_100m(rows, backend, dry_run=False)
        row_outputs = [row for row in scored.get('rows') or [] if isinstance(row, dict)]
        summary = runner.summarize_predictions(row_outputs)
        macro_scores.append(float(summary.get('accuracy') or 0.0))
        total_correct += int(summary.get('correct') or 0)
        total_rows += int(summary.get('rows') or 0)
        unsolved = [row for row in row_outputs if row.get('correct') is not True]
        result = {
            'bundle_id': bundle_id,
            'language_family': language,
            'rows': row_outputs,
            'summary': summary,
            'unsolved_rows': unsolved,
        }
        results.append(result)
        bundle_cards.append({
            'bundle_id': bundle_id,
            'language_family': language,
            'rows': int(summary.get('rows') or 0),
            'correct': int(summary.get('correct') or 0),
            'accuracy': float(summary.get('accuracy') or 0.0),
            'bundle_solved': int(summary.get('correct') or 0) == int(summary.get('rows') or 0) and int(summary.get('rows') or 0) > 0,
            'unsolved_perspectives': [str(row.get('perspective') or '') for row in unsolved],
        })
        per_language_rows[language].append(bundle_cards[-1])
    per_language = {}
    for language, cards in sorted(per_language_rows.items()):
        rows = sum(int(card['rows']) for card in cards)
        correct = sum(int(card['correct']) for card in cards)
        per_language[language] = {
            'bundles': len(cards),
            'rows': rows,
            'macro_accuracy': mean([float(card['accuracy']) for card in cards]),
            'micro_accuracy': (correct / rows) if rows else 0.0,
            'bundle_solved': sum(1 for card in cards if card['bundle_solved']),
        }
    audit = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': bool(results),
        'sources': {
            'payload': display(PAYLOAD),
            'runtime_bundle': display(RUNTIME_BUNDLE),
            'runner': display(RUNNER),
        },
        'claim_scope': 'exact admitted 8-bundle row-level audit of the saved stage10224 runtime only; no Gemma rerun',
        'backend': backend,
        'metrics': {
            'bundle_count': len(bundle_cards),
            'row_count': total_rows,
            'macro_accuracy': mean(macro_scores),
            'micro_accuracy': (total_correct / total_rows) if total_rows else 0.0,
            'bundle_solved': sum(1 for card in bundle_cards if card['bundle_solved']),
            'unsolved_bundle_count': sum(1 for card in bundle_cards if not card['bundle_solved']),
        },
        'per_language': per_language,
        'bundle_cards': bundle_cards,
        'results': results,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding='utf-8')
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'passed': audit['passed'], 'artifact': display(AUDIT), 'metrics': audit['metrics'], 'per_language': per_language}, indent=2, sort_keys=True) + "\n", encoding='utf-8')
    print(json.dumps({'stage': STAGE, 'passed': audit['passed'], 'artifact': display(AUDIT), 'metrics': audit['metrics'], 'per_language': per_language}, indent=2))


if __name__ == '__main__':
    main()
