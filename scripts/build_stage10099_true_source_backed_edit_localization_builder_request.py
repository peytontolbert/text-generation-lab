#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10099
NAME = "stage10099_true_source_backed_edit_localization_builder_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "true_source_backed_edit_localization_builder_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_EDIT_LOCALIZATION_BUILDER_REQUEST_STAGE10099.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
ANCESTRY = ROOT / "runs/local/artifacts/stage10098_locked_source_subset_synthetic_ancestry_audit/locked_source_subset_synthetic_ancestry_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding='utf-8')


def build() -> dict[str, Any]:
    ancestry = load_json(ANCESTRY)
    metrics = {
        'replacement_builder_required': bool(((ancestry.get('claim_boundary') or {}).get('replacement_builder_required'))),
        'upstream_synthetic_task_observation_count': ((ancestry.get('metrics') or {}).get('unique_synthetic_task_observations_in_locked_subset')),
        'upstream_synthetic_visible_evidence_count': ((ancestry.get('metrics') or {}).get('unique_synthetic_visible_evidence_strings_in_locked_subset')),
    }
    failures: list[str] = []
    if metrics['replacement_builder_required'] is not True:
        failures.append('replacement_builder_not_required_flag_missing')
    request = {
        'stage': STAGE,
        'name': NAME,
        'passed': not failures,
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'artifacts': {
            'synthetic_ancestry_audit': display(ANCESTRY),
        },
        'intent': 'Replace the synthetic stage8636->stage8765 edit-localization path with a truly source-backed builder that emits maintainer-visible failure text, traces, candidate paths, and snippets from real external graph or session evidence.',
        'requirements': [
            'input roots must come from real external graph/session evidence rather than stage8636 synthetic templates',
            'candidate_paths and trace_excerpt must be derived from real source artifacts',
            'relevant_snippets must come from real repo spans or session-backed code excerpts',
            'source-heldout and anti-cheat lineage must be preserved per row',
            'builder must cover python, rust, c_cpp, and web_js_ts_html before multilingual maintainer claims',
        ],
        'claim_boundary': {
            'current_stage8765_path_salvageable_for_maintainer_claim': False,
            'true_source_backed_builder_required_now': True,
        },
        'metrics': metrics,
        'failures': failures,
        'next_best_step': 'Implement the replacement source-backed builder on real external graph/session roots instead of continuing to extend the synthetic stage8765 lineage.',
    }
    return request


def write_doc(request: dict[str, Any]) -> None:
    lines = [
        '# Stage10099 True Source-Backed Edit Localization Builder Request',
        '',
        f"Passed: `{request['passed']}`",
        '',
        'This request formalizes the replacement of the synthetic stage8636 -> stage8765 path. The next builder must originate from real external graph or session evidence and emit maintainer-visible failure, trace, path, and snippet fields directly.',
        '',
        f"Next: {request['next_best_step']}",
        '',
    ]
    DOC.write_text("\n".join(lines), encoding='utf-8')


def main() -> None:
    request = build()
    write_json(REQUEST, request)
    summary = {'stage': STAGE, 'stage_name': NAME, 'passed': request['passed'], 'artifacts': request['artifacts'], 'metrics': request['metrics'], 'next_best_step': request['next_best_step']}
    write_json(SUMMARY, summary)
    write_doc(request)
    update_registry(summary)
    print(json.dumps({'stage': STAGE, 'passed': request['passed'], 'failures': request['failures']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
