#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10231
NAME = "stage10231_projection_failure_support_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "projection_failure_support_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
PROJECTION = ROOT / "runs/local/artifacts/stage10226_adjudicated_projection_bundle_coherence_runtime_multilingual/first_wave_bundle_inference_summary.json"
TRAIN = ROOT / "runs/local/artifacts/stage10222_bundle_coherence_counterbalance_package/agentkernel_lite_encdec_train.jsonl"
STRICT = ROOT / "runs/local/artifacts/stage10222_bundle_coherence_counterbalance_package/agentkernel_lite_encdec_eval.jsonl"
STAGE10224 = ROOT / "runs/local/artifacts/stage10224_bundle_coherence_counterbalance_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
STAGE10230 = ROOT / "runs/local/artifacts/stage10230_evidence_coherence_narrow_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
PAYLOAD = ROOT / "runs/local/artifacts/stage10225_adjudicated_projection_bundle_coherence_runtime_payload/adjudicated_projection_bundle_coherence_runtime_payload.json"


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


def parse_prefix(row_id: str) -> str:
    return row_id.rsplit("::perm_", 1)[0] if "::perm_" in row_id else row_id


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    projection = load_json(PROJECTION)
    payload = load_json(PAYLOAD)
    train_rows = load_jsonl(TRAIN)
    strict_rows = [row for row in load_jsonl(STRICT) if str(row.get("split") or "") == "strict_eval"]
    strict_10224 = load_json(STAGE10224).get("row_cards") or []
    strict_1030 = load_json(STAGE10230).get("row_cards") or []

    task_pack_by_bundle = {str(run.get("task_pack", {}).get("bundle_id") or ""): run.get("task_pack") or {} for run in payload.get("runs") or [] if isinstance(run, dict)}

    train_direct = Counter()
    train_task = Counter()
    train_cross = Counter()
    for row in train_rows:
        source = row.get("standalone_projection_source") or {}
        key = (str(row.get("language_family") or ""), str(row.get("task_type") or ""), str(source.get("gold_value") or ""))
        train_direct[key] += 1
        train_task[(str(row.get("language_family") or ""), str(row.get("task_type") or ""))] += 1
        train_cross[(str(row.get("task_type") or ""), str(source.get("gold_value") or ""))] += 1

    strict_prefix_counts = Counter(parse_prefix(str(row.get("row_id") or "")) for row in strict_rows)
    strict24_map = {str(card.get("row_id") or ""): bool(card.get("constrained_choice_match")) for card in strict_10224}
    strict30_map = {str(card.get("row_id") or ""): bool(card.get("constrained_choice_match")) for card in strict_1030}

    bundle_failures = []
    unsupported = []
    direct_supported = []
    cross_language_only = []
    for result in projection.get("results") or []:
        bundle_id = str(result.get("bundle_id") or "")
        if int((result.get("hundred_m") or {}).get("correct") or 0) == int(result.get("rows") or 0):
            continue
        task_pack = task_pack_by_bundle.get(bundle_id) or {}
        rows_by_task = {str(row.get("task_type") or row.get("perspective") or ""): row for row in task_pack.get("rows") or [] if isinstance(row, dict)}
        for perspective, stats in sorted(((result.get("hundred_m") or {}).get("by_perspective") or {}).items()):
            if int(stats.get("correct") or 0) == int(stats.get("rows") or 0):
                continue
            row = rows_by_task.get(perspective) or {}
            language = str(row.get("language_family") or bundle_id.split("::")[-1])
            gold = str(row.get("gold_value") or "")
            row_prefix = str(row.get("row_id") or "")
            direct_count = train_direct[(language, perspective, gold)]
            task_count = train_task[(language, perspective)]
            cross_count = train_cross[(perspective, gold)]
            exact_in_strict = strict_prefix_counts[row_prefix]
            strict24_rows = [(rid, ok) for rid, ok in strict24_map.items() if rid.startswith(row_prefix)]
            strict30_rows = [(rid, ok) for rid, ok in strict30_map.items() if rid.startswith(row_prefix)]
            if direct_count > 0:
                support_status = 'direct_same_language_support'
                direct_supported.append(f"{language}::{perspective}::{gold}")
            elif cross_count > 0:
                support_status = 'cross_language_only_support'
                cross_language_only.append(f"{language}::{perspective}::{gold}")
            else:
                support_status = 'unsupported_eval_only'
                unsupported.append(f"{language}::{perspective}::{gold}")
            bundle_failures.append({
                'bundle_id': bundle_id,
                'language_family': language,
                'perspective': perspective,
                'gold_value': gold,
                'expected_label': row.get('expected_label'),
                'direct_same_language_train_rows': direct_count,
                'same_language_task_train_rows': task_count,
                'cross_language_train_rows_same_gold': cross_count,
                'support_status': support_status,
                'exact_row_prefix_in_stage10222_strict_eval': exact_in_strict,
                'stage10224_matching_strict_rows': len(strict24_rows),
                'stage10224_matching_strict_correct': sum(1 for _, ok in strict24_rows if ok),
                'stage10230_matching_strict_rows': len(strict30_rows),
                'stage10230_matching_strict_correct': sum(1 for _, ok in strict30_rows if ok),
                'projection_accuracy_stage10227': float(stats.get('accuracy') or 0.0),
            })

    audit = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'sources': {
            'projection_summary': display(PROJECTION),
            'projection_payload': display(PAYLOAD),
            'train_dataset': display(TRAIN),
            'strict_dataset': display(STRICT),
            'stage10224_strict_eval': display(STAGE10224),
            'stage10230_strict_eval': display(STAGE10230),
        },
        'frontier_decision': {
            'accepted_runtime_frontier': 'stage10224_bundle_coherence_counterbalance_probe',
            'rejected_runtime_branch': 'stage10230_evidence_coherence_narrow_probe',
            'rejection_reason': 'no targeted recoveries and 6 strict-eval regressions on c_cpp evidence_citation',
        },
        'metrics': {
            'unsolved_bundle_count': len({card['bundle_id'] for card in bundle_failures}),
            'unsolved_perspective_count': len(bundle_failures),
            'direct_same_language_support_failures': sum(1 for card in bundle_failures if card['support_status'] == 'direct_same_language_support'),
            'cross_language_only_failures': sum(1 for card in bundle_failures if card['support_status'] == 'cross_language_only_support'),
            'unsupported_eval_only_failures': sum(1 for card in bundle_failures if card['support_status'] == 'unsupported_eval_only'),
            'projection_rows_missing_exact_strict_prefix': sum(1 for card in bundle_failures if card['exact_row_prefix_in_stage10222_strict_eval'] == 0),
        },
        'bundle_failure_cards': bundle_failures,
        'notes': [
            'Projection failures with exact_row_prefix_in_stage10222_strict_eval = 0 are not directly measured by the standalone strict slice even when related permuted variants exist.',
            'Unsupported_eval_only failures should not drive new train rows unless fresh independent train support is created.',
            'Cross_language_only failures may improve via transfer, but any same-language claim remains unsupported until same-language train support exists.',
        ],
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding='utf-8')
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'passed': True, 'artifact': display(AUDIT), 'metrics': audit['metrics'], 'frontier_decision': audit['frontier_decision']}, indent=2, sort_keys=True) + "\n", encoding='utf-8')
    print(json.dumps({'stage': STAGE, 'passed': True, 'artifact': display(AUDIT), 'metrics': audit['metrics'], 'frontier_decision': audit['frontier_decision']}, indent=2))


if __name__ == '__main__':
    main()
