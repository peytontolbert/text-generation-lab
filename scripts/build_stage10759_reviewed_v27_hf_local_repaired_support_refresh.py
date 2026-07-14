#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'

STAGE = 10759
NAME = 'stage10759_reviewed_v27_hf_local_repaired_support_refresh'
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / 'reviewed_v27_hf_local_repaired_support_refresh.json'
TRAIN_JSONL = OUT_DIR / 'agentkernel_lite_encdec_train.jsonl'
VALIDATION_JSONL = OUT_DIR / 'agentkernel_lite_encdec_validation.jsonl'
STRICT_JSONL = OUT_DIR / 'agentkernel_lite_encdec_strict_eval.jsonl'
STRESS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_stress_eval.jsonl'
ROWS_JSONL = OUT_DIR / 'reviewed_v27_hf_local_repaired_support_rows.jsonl'
RUN_SUMMARY = ROOT / 'runs' / 'summaries' / f'{NAME}.json'

BASE_PACKAGE = ARTIFACTS / 'stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package' / 'reviewed_v27_plus_cpp_bootstrap_train_support_package.json'
BASE_TRAIN = ARTIFACTS / 'stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package' / 'agentkernel_lite_encdec_train.jsonl'
BASE_VALIDATION = ARTIFACTS / 'stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package' / 'agentkernel_lite_encdec_validation.jsonl'
BASE_STRICT = ARTIFACTS / 'stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package' / 'agentkernel_lite_encdec_strict_eval.jsonl'
BASE_STRESS = ARTIFACTS / 'stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package' / 'agentkernel_lite_encdec_stress_eval.jsonl'
HF_LOCAL_ROWS = ARTIFACTS / 'stage10501_hf_local_repaired_compact_bounded_projection' / 'hf_local_repaired_compact_bounded_rows.jsonl'
PROMOTION_AUDIT = ARTIFACTS / 'stage10758_python_residual_packet_promotability_audit' / 'python_residual_packet_promotability_queue.jsonl'

REMOVE_ROW_IDS = {
    'stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662::python_implementation_vs_implementation::reviewed_v27_successor'
}
REMOVE_SOURCE_BUNDLE_IDS = {
    'stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python'
}


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


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


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or 'unknown') for row in rows).items()))


def main() -> None:
    base_package = load_json(BASE_PACKAGE)
    base_train = load_jsonl(BASE_TRAIN)
    validation_rows = load_jsonl(BASE_VALIDATION)
    strict_rows = load_jsonl(BASE_STRICT)
    stress_rows = load_jsonl(BASE_STRESS)
    hf_rows = load_jsonl(HF_LOCAL_ROWS)
    promotion_rows = load_jsonl(PROMOTION_AUDIT)

    promotable = [row for row in promotion_rows if row.get('decision') == 'promotable_via_existing_repaired_packet']
    if len(promotable) != 1:
        raise SystemExit('expected_exactly_one_promotable_python_lane')

    filtered_base_train = [
        row for row in base_train
        if str(row.get('row_id') or '') not in REMOVE_ROW_IDS
        and str(row.get('source_bundle_id') or '') not in REMOVE_SOURCE_BUNDLE_IDS
    ]

    existing_row_ids = {str(row.get('row_id') or '') for row in filtered_base_train}
    refreshed_hf_rows = [row for row in hf_rows if str(row.get('row_id') or '') not in existing_row_ids]
    train_rows = filtered_base_train + refreshed_hf_rows

    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(ROWS_JSONL, refreshed_hf_rows)

    removed_rows = [row for row in base_train if str(row.get('row_id') or '') in REMOVE_ROW_IDS]

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': bool(train_rows) and bool(strict_rows),
        'decision': 'reviewed_v27_hf_local_repaired_support_refresh_ready',
        'claim_boundary': [
            'This refresh changes train support only; validation, strict, and stress rows stay unchanged from the current reviewed v2.7 plus C++ bootstrap frontier.',
            'The repaired hf_local lane is admitted only as train-support refresh and not as a heldout improvement claim.',
            'The compressed agentkernel successor lane is explicitly removed from probe-ready train support until a non-compressed repaired packet exists.',
        ],
        'source_artifacts': {
            'base_package': rel(BASE_PACKAGE),
            'hf_local_repaired_rows': rel(HF_LOCAL_ROWS),
            'promotion_audit': rel(PROMOTION_AUDIT),
        },
        'package_diff': {
            'base_train_rows': len(base_train),
            'refreshed_train_rows': len(train_rows),
            'removed_train_row_ids': [str(row.get('row_id') or '') for row in removed_rows],
            'added_hf_local_row_ids': [str(row.get('row_id') or '') for row in refreshed_hf_rows],
        },
        'metrics': {
            'train_rows': len(train_rows),
            'validation_rows': len(validation_rows),
            'strict_eval_rows': len(strict_rows),
            'stress_rows': len(stress_rows),
            'train_language_counts': count_by(train_rows, 'language_family'),
            'train_task_counts': count_by(train_rows, 'task_type'),
            'train_repo_counts': count_by(train_rows, 'repo_id'),
        },
        'python_lane_state': {
            'hf_local_repaired_lane_active': True,
            'agentkernel_compressed_lane_removed': True,
            'promotable_support_bundle': promotable[0]['repaired_packet_bundle_id'],
            'promotable_support_packet': promotable[0]['repaired_packet_path'],
            'promotable_support_packet_audit': promotable[0]['repaired_packet_audit'],
        },
        'outputs': {
            'train_rows': rel(TRAIN_JSONL),
            'validation_rows': rel(VALIDATION_JSONL),
            'strict_rows': rel(STRICT_JSONL),
            'stress_rows': rel(STRESS_JSONL),
            'support_rows': rel(ROWS_JSONL),
            'package_json': rel(PACKAGE_JSON),
        },
        'next_best_step': 'Run a new support-only probe from the preserved runtime using this refreshed package and require improvement beyond 22/24 with zero strict regressions before any promotion.',
        'base_package_metrics_snapshot': base_package.get('metrics'),
    }

    write_json(PACKAGE_JSON, payload)
    write_json(
        RUN_SUMMARY,
        {
            'stage': STAGE,
            'passed': True,
            'decision': payload['decision'],
            'package': rel(PACKAGE_JSON),
            'train_rows': rel(TRAIN_JSONL),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
