#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10098
NAME = "stage10098_locked_source_subset_synthetic_ancestry_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "locked_source_subset_synthetic_ancestry_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCKED_SOURCE_SUBSET_SYNTHETIC_ANCESTRY_AUDIT_STAGE10098.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LOCKED_ROWS = ROOT / "runs/local/artifacts/stage10095_locked_source_realistic_successor_request/locked_source_realistic_successor_rows.jsonl"
STAGE8765 = ROOT / "runs/local/artifacts/stage8765_source_backed_edit_localization_candidate_manifest/source_backed_edit_localization_candidate_manifest.jsonl"
STAGE8636 = ROOT / "runs/local/artifacts/stage8636_edit_localization_neutral_manifest/edit_localization_neutral_manifest.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)), "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build() -> dict[str, Any]:
    locked_rows = load_jsonl(LOCKED_ROWS)
    stage8765_rows = load_jsonl(STAGE8765)
    stage8636_rows = load_jsonl(STAGE8636)
    stage8765_by_row = {str(row.get('row_id') or ''): row for row in stage8765_rows}
    ancestry_matches = []
    for row in locked_rows:
        source_row_id = str(row.get('source_row_id') or '')
        src = stage8765_by_row.get(source_row_id)
        if src:
            ancestry_matches.append(src)
    synthetic_task_obs = sorted({str(((row.get('corrupted_state') if isinstance(row.get('corrupted_state'), dict) else {}).get('task_observation') or '')) for row in ancestry_matches})
    synthetic_visible_evidence = sorted({str(((row.get('corrupted_state') if isinstance(row.get('corrupted_state'), dict) else {}).get('visible_locality_evidence') or '')) for row in ancestry_matches})
    metrics = {
        'locked_rows': len(locked_rows),
        'stage8765_ancestry_matches': len(ancestry_matches),
        'stage8636_rows': len(stage8636_rows),
        'unique_synthetic_task_observations_in_locked_subset': len(synthetic_task_obs),
        'unique_synthetic_visible_evidence_strings_in_locked_subset': len(synthetic_visible_evidence),
        'synthetic_task_observations': synthetic_task_obs,
        'synthetic_visible_evidence_strings': synthetic_visible_evidence,
        'all_locked_rows_trace_to_stage8636_neutral_manifest': len(ancestry_matches) == len(locked_rows),
    }
    failures: list[str] = []
    if metrics['locked_rows'] != 18:
        failures.append('locked_rows_not_18')
    if metrics['stage8765_ancestry_matches'] != 18:
        failures.append('stage8765_ancestry_not_complete')
    findings = [
        'Every row in the locked-source bootstrap subset traces back to the stage8765 candidate manifest.',
        'Stage8765 itself was built directly from the stage8636 neutral manifest, which is synthetic and uses a small fixed task/evidence template family.',
        'That means the locked-source subset is honest about heldout wrappers and lineage bookkeeping, but it is not an expert-maintainer packet and cannot be promoted by graph materialization alone.',
    ]
    next_best_step = 'Build a truly source-backed edit-localization candidate builder from external repo/session evidence instead of continuing to adapt the synthetic stage8636 -> stage8765 lineage.'
    return {
        'stage': STAGE,
        'name': NAME,
        'passed': not failures,
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'artifacts': {
            'locked_rows': display(LOCKED_ROWS),
            'stage8765_manifest': display(STAGE8765),
            'stage8636_manifest': display(STAGE8636),
        },
        'claim_boundary': {
            'locked_subset_is_true_maintainer_eval': False,
            'reason': 'The locked subset inherits from the synthetic stage8636 neutral manifest through stage8765, so its visible task/evidence content is not genuine repository maintenance evidence.',
            'replacement_builder_required': True,
        },
        'metrics': metrics,
        'findings': findings,
        'failures': failures,
        'next_best_step': next_best_step,
    }


def write_doc(packet: dict[str, Any]) -> None:
    metrics = packet['metrics']
    lines = [
        '# Stage10098 Locked Source Subset Synthetic Ancestry Audit',
        '',
        f"Passed: `{packet['passed']}`",
        f"Locked rows: `{metrics['locked_rows']}`",
        f"Stage8765 ancestry matches: `{metrics['stage8765_ancestry_matches']}`",
        f"Unique synthetic task observations in subset: `{metrics['unique_synthetic_task_observations_in_locked_subset']}`",
        '',
        'The locked-source subset is still downstream of the synthetic stage8636 neutral manifest. That means it cannot become a real maintainer-grade benchmark simply by resolving graph handles or attaching more review cards.',
        '',
        f"Next: {packet['next_best_step']}",
        '',
    ]
    DOC.write_text("\n".join(lines), encoding='utf-8')


def main() -> None:
    packet = build()
    write_json(PACKET, packet)
    summary = {'stage': STAGE, 'stage_name': NAME, 'passed': packet['passed'], 'artifacts': packet['artifacts'], 'metrics': packet['metrics'], 'next_best_step': packet['next_best_step']}
    write_json(SUMMARY, summary)
    write_doc(packet)
    update_registry(summary)
    print(json.dumps({'stage': STAGE, 'passed': packet['passed'], 'failures': packet['failures']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
