#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10095
NAME = "stage10095_locked_source_realistic_successor_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "locked_source_realistic_successor_request.json"
ROWS = OUT_DIR / "locked_source_realistic_successor_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCKED_SOURCE_REALISTIC_SUCCESSOR_REQUEST_STAGE10095.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE = ROOT / "runs/local/artifacts/stage10093_canonical_source_heldout_realistic_source_backed_successor_request/canonical_source_heldout_realistic_source_backed_successor_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalize_root(source_row_id: str) -> str:
    match = re.search(r"(stage8765_row_[0-9a-f]+)", source_row_id)
    return match.group(1) if match else source_row_id


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)), "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding='utf-8')


def build() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = load_jsonl(SOURCE)
    rows = [row for row in source_rows if row.get('locked_eval_source') is True]
    normalized = sorted({normalize_root(str(row.get('source_row_id') or '')) for row in rows})
    metrics = {
        'rows': len(rows),
        'languages': dict(sorted(Counter(str(row.get('language_family') or '') for row in rows).items())),
        'compare_subset_split_counts': dict(sorted(Counter(str(row.get('compare_subset_split') or '') for row in rows).items())),
        'hidden_target_families': dict(sorted(Counter(str(row.get('hidden_target_family') or '') for row in rows).items())),
        'normalized_stage8765_roots': len(normalized),
    }
    failures: list[str] = []
    if metrics['rows'] != 18:
        failures.append('locked_source_rows_not_18')
    next_best_step = 'Use this 18-row locked-source subset as the first maintainer-grade source-materialization target while separately replenishing more independent locked-source roots for the other languages.'
    request = {
        'stage': STAGE,
        'name': NAME,
        'passed': not failures,
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'artifacts': {
            'source_request_rows': display(SOURCE),
            'subset_rows': display(ROWS),
        },
        'intent': 'Narrow the next realistic source-backed successor to the already locked eval-source rows so maintainer-grade evidence can be materialized without pretending the full 55-row bank is ready.',
        'claim_boundary': {
            'full_multilingual_successor_ready': False,
            'locked_subset_candidate_ready': True,
            'reason': 'This subset is only 18 rows and covers Python plus C/C++, so it is an honest bootstrap subset rather than a final four-language maintainer eval.',
        },
        'metrics': metrics,
        'failures': failures,
        'next_best_step': next_best_step,
    }
    return request, rows


def write_doc(request: dict[str, Any]) -> None:
    metrics = request['metrics']
    lines = [
        '# Stage10095 Locked Source Realistic Successor Request',
        '',
        f"Passed: `{request['passed']}`",
        f"Locked-source rows: `{metrics['rows']}`",
        f"Languages: `{metrics['languages']}`",
        '',
        'This request narrows the next realistic source-backed successor to the 18 rows that are already marked `locked_eval_source`. That is not the final multilingual maintainer benchmark, but it is the honest subset that can be materialized first without overstating the readiness of the full 55-row bank.',
        '',
        'Next: materialize real failure/trace/snippet/candidate evidence for these 18 rows, then replenish more locked-source Rust and Web roots to restore four-language coverage on a maintainer-grade surface.',
        '',
    ]
    DOC.write_text("\n".join(lines), encoding='utf-8')


def main() -> None:
    request, rows = build()
    write_json(REQUEST, request)
    write_jsonl(ROWS, rows)
    summary = {"stage": STAGE, "stage_name": NAME, "passed": request['passed'], "artifacts": request['artifacts'], "metrics": request['metrics'], "next_best_step": request['next_best_step']}
    write_json(SUMMARY, summary)
    write_doc(request)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": request['passed'], "failures": request['failures']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
