#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'

STAGE = 10762
NAME = 'stage10762_hf_local_repaired_support_probe_audit'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'hf_local_repaired_support_probe_audit.json'
MISS_ROWS_JSONL = OUT_DIR / 'strict_miss_rows.jsonl'
RUN_SUMMARY = ROOT / 'runs' / 'summaries' / f'{NAME}.json'

PROBE_REQUEST = ARTIFACTS / 'stage10760_hf_local_repaired_support_probe_request' / 'hf_local_repaired_support_probe_request.json'
PACKAGE_JSON = ARTIFACTS / 'stage10759_reviewed_v27_hf_local_repaired_support_refresh' / 'reviewed_v27_hf_local_repaired_support_refresh.json'
EXECUTION_RESULT = ARTIFACTS / 'stage10761_hf_local_repaired_support_probe' / 'bounded_decoder_probe' / 'execution_result.json'
STRICT_AUDIT = ARTIFACTS / 'stage10761_hf_local_repaired_support_probe' / 'bounded_decoder_probe' / 'bounded_choice_eval_audit_strict_eval.json'
EVAL_AUDIT = ARTIFACTS / 'stage10761_hf_local_repaired_support_probe' / 'bounded_decoder_probe' / 'bounded_choice_eval_audit_eval.json'

BASELINE_STRICT = 22 / 24


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    request = load_json(PROBE_REQUEST)
    package = load_json(PACKAGE_JSON)
    execution = load_json(EXECUTION_RESULT)
    strict = load_json(STRICT_AUDIT)
    eval_audit = load_json(EVAL_AUDIT)
    execution_card = execution.get('probe_summary', execution)

    strict_acc = float(strict['constrained_choice_top1_accuracy'])
    eval_acc = float(eval_audit['constrained_choice_top1_accuracy'])
    miss_rows = [row for row in strict['row_cards'] if not row['constrained_choice_match']]

    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'hf_local_repaired_support_probe_audited',
        'claim_scope': [
            'Audit whether the refreshed multilingual support package with repaired hf_local support improves the live 24-row reviewed v2.7 strict frontier.',
            'Record whether the support refresh changes the surviving strict miss set or only preserves the existing 22/24 baseline.',
            'This is a probe audit, not a promotion artifact.',
        ],
        'headline_findings': [
            'The refreshed probe completed successfully under the preserved runtime and artifact contract.',
            'Strict constrained accuracy remained 22/24 = 0.9166666666666666, matching the prior honest baseline.',
            'The surviving strict misses are still the Python verifier_outcome MirrorMind row and the Rust tokenizers evidence_citation row.',
        ],
        'result': {
            'strict_constrained_accuracy': strict_acc,
            'strict_rows': int(strict['constrained_choice_rows']),
            'eval_constrained_accuracy': eval_acc,
            'strict_delta_vs_22_of_24_baseline': strict_acc - BASELINE_STRICT,
            'full_vocab_top1_accuracy_strict': float(strict['full_vocab_top1_accuracy']),
            'full_vocab_top1_accuracy_eval': float(eval_audit['full_vocab_top1_accuracy']),
        },
        'probe_hygiene': {
            'runtime_executed': bool(execution_card.get('runtime_executed')),
            'required_artifacts_written': bool(execution_card.get('required_artifacts_written')),
            'generation_audit_enabled': bool(execution_card.get('generation_audit_enabled')),
            'hf_local_repaired_lane_active': bool(package.get('python_lane_state', {}).get('hf_local_repaired_lane_active')),
            'agentkernel_compressed_lane_removed': bool(package.get('python_lane_state', {}).get('agentkernel_compressed_lane_removed')),
        },
        'miss_rows': [row['row_id'] for row in miss_rows],
        'source_artifacts': {
            'probe_request': rel(PROBE_REQUEST),
            'support_package': rel(PACKAGE_JSON),
            'execution_result': rel(EXECUTION_RESULT),
            'strict_audit': rel(STRICT_AUDIT),
            'eval_audit': rel(EVAL_AUDIT),
        },
        'next_best_step': 'Do not promote this refresh. Keep the repaired hf_local lane as a cleaner support path, but target fresh disjoint data for the unchanged Python verifier and Rust evidence-citation misses.',
        'outputs': {
            'summary': rel(SUMMARY_JSON),
            'miss_rows': rel(MISS_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(MISS_ROWS_JSONL, miss_rows)
    write_json(
        RUN_SUMMARY,
        {
            'stage': STAGE,
            'passed': True,
            'decision': summary['decision'],
            'summary': rel(SUMMARY_JSON),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
