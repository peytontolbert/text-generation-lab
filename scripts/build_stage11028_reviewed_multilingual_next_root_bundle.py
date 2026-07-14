#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11028
NAME = "stage11028_reviewed_multilingual_next_root_bundle"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "reviewed_multilingual_next_root_bundle.json"
COMBINED_ROWS = OUT_DIR / "bundle_rows.jsonl"
SUPPORT_ROWS = OUT_DIR / "train_support_rows.jsonl"
CANDIDATE_ROWS = OUT_DIR / "strict_candidate_rows.jsonl"
SPECS_JSONL = OUT_DIR / "reviewed_multilingual_next_root_specs.jsonl"

SCALING_ATLAS = ARTIFACTS / "stage10417_multilingual_reviewed_scaling_atlas" / "multilingual_reviewed_scaling_atlas.json"
REQUEST_ROWS = ARTIFACTS / "stage11027_next_source_materialization_request" / "request_rows.jsonl"

from scripts.build_stage10934_explicit_verifier_ledger_support_package import (
    SOURCE_ROW_FILES,
    build_variant_rows,
    find_source_row,
    load_gold_by_perspective,
    load_jsonl,
    rel as base_rel,
)
from scripts.build_stage10938_explicit_verifier_ledger_strict_candidates import build_strict_row


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_specs() -> list[dict[str, Any]]:
    atlas = json.loads(SCALING_ATLAS.read_text(encoding="utf-8"))
    admitted = {str(row.get("bundle_id")): row for row in atlas.get("admitted_bundle_rows") or []}
    requests = [row for row in load_jsonl(REQUEST_ROWS) if row.get("request_kind") == "reviewed_bundle_materialization"]
    specs: list[dict[str, Any]] = []
    for row in requests:
        bundle_id = str(row.get("bundle_id") or "")
        atlas_row = admitted.get(bundle_id)
        if atlas_row is None:
            continue
        packet_dir = atlas_row.get("packet_dir")
        if not packet_dir:
            continue
        spec = {
            "queue_id": f"reviewed_next::{bundle_id.replace('::', '__')}",
            "language_family": atlas_row.get("language_family"),
            "repo_id": atlas_row.get("repo_id"),
            "source_bundle_id": bundle_id,
            "packet_dir": packet_dir,
            "current_checked_row_id": None,
            "current_checked_target_value": None,
            "gold_answer_kind": "candidate_or_abstain",
            "gold_answer_value": None,
            "selected_tests": list(atlas_row.get("selected_tests") or []),
            "candidate_paths": list(atlas_row.get("candidate_paths") or []),
            "visible_evidence_keys": list(atlas_row.get("visible_evidence_keys") or []),
            "reviewer_rationale": str(atlas_row.get("decision_rationale") or ""),
            "anti_cheat_challenge_families": [
                "candidate_path_or_order_bias",
                "cross_repo_analogue_leakage",
                "hidden_reference_or_metadata_leakage",
                "perspective_paraphrase_collapse",
                "template_and_surface_prior_shortcuts",
            ],
            "materialization_requirements": [
                "Preserve selected-test anchors as visible verifier evidence where available.",
                "Do not expose target path strings before options.",
                "Retain candidate-surface distractors so the row tests evidence-role choice rather than lexical matching.",
                "Keep new roots disjoint from the frozen 23-row overlay claim path until explicitly admitted.",
            ],
            "request_priority": row.get("priority"),
            "request_objective": row.get("objective"),
            "request_kind": row.get("request_kind"),
        }
        specs.append(spec)
    return specs


def enrich_row(spec: dict[str, Any], row: dict[str, Any], *, candidate: bool) -> dict[str, Any]:
    updated = dict(row)
    updated["bundle_id"] = f"stage11028::{spec['queue_id']}::reviewed_multilingual_next_root"
    updated["candidate_queue_id"] = spec.get("queue_id")
    updated["selected_tests"] = list(spec.get("selected_tests") or [])
    updated["candidate_paths"] = list(spec.get("candidate_paths") or [])
    updated["visible_evidence_keys"] = list(spec.get("visible_evidence_keys") or [])
    updated["materialization_requirements"] = list(spec.get("materialization_requirements") or [])
    updated["request_priority"] = spec.get("request_priority")
    updated["request_objective"] = spec.get("request_objective")
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["anti_cheat_challenge_families"] = list(spec.get("anti_cheat_challenge_families") or [])
    anti_cheat["reviewed_multilingual_next_root"] = True
    anti_cheat["same_surface_eval_admissible"] = False
    if candidate:
        anti_cheat["candidate_only"] = True
    updated["anti_cheat"] = anti_cheat
    projection = dict(updated.get("standalone_projection_source") or {})
    opaque_options = [dict(item) for item in (updated.get("opaque_options") or []) if isinstance(item, dict)]
    projection["opaque_options"] = opaque_options
    projection["option_values"] = [str(item.get("value") or "") for item in opaque_options]
    projection["option_labels"] = [str(item.get("label") or "") for item in opaque_options]
    projection["visible_evidence_keys"] = list(spec.get("visible_evidence_keys") or [])
    projection["selected_tests"] = list(spec.get("selected_tests") or [])
    projection["candidate_paths"] = list(spec.get("candidate_paths") or [])
    projection["reviewer_rationale"] = spec.get("reviewer_rationale")
    projection["anti_cheat_challenge_families"] = list(spec.get("anti_cheat_challenge_families") or [])
    projection["bundle_stage"] = STAGE
    projection["request_objective"] = spec.get("request_objective")
    updated["standalone_projection_source"] = projection
    return updated


def main() -> None:
    specs = load_specs()
    corpus: list[dict[str, Any]] = []
    for path in SOURCE_ROW_FILES:
        corpus.extend(load_jsonl(path))

    support_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    bundle_rows: list[dict[str, Any]] = []
    bundle_index: list[dict[str, Any]] = []

    for spec in specs:
        source_row = find_source_row(spec, corpus)
        gold_by_perspective = load_gold_by_perspective(spec)
        queue_support_rows: list[dict[str, Any]] = []
        for row in build_variant_rows(spec, source_row, gold_by_perspective):
            enriched = enrich_row(spec, row, candidate=False)
            support_rows.append(enriched)
            bundle_rows.append(enriched)
            queue_support_rows.append(enriched)
        candidate = enrich_row(spec, build_strict_row(spec, source_row, gold_by_perspective), candidate=True)
        candidate_rows.append(candidate)
        bundle_rows.append(candidate)
        bundle_index.append(
            {
                "queue_id": spec.get("queue_id"),
                "repo_id": spec.get("repo_id"),
                "language_family": spec.get("language_family"),
                "source_bundle_id": spec.get("source_bundle_id"),
                "request_priority": spec.get("request_priority"),
                "request_objective": spec.get("request_objective"),
                "selected_tests": spec.get("selected_tests"),
                "candidate_row_id": candidate.get("row_id"),
                "support_row_ids": [row.get("row_id") for row in queue_support_rows],
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(bundle_rows),
        "decision": "reviewed_multilingual_next_root_bundle_ready",
        "claim_scope": [
            "Materialize the exact reviewed Python/C++/web roots named in stage11027 into support-only evidence rows plus explicit-ledger candidate rows.",
            "Provide the next honest multilingual bundle beyond the immediate evidence queue without pretending the rows are headline-admitted strict eval.",
        ],
        "source_artifacts": {
            "request_rows_jsonl": rel(REQUEST_ROWS),
            "reviewed_scaling_atlas": rel(SCALING_ATLAS),
            "source_row_files": [base_rel(path) for path in SOURCE_ROW_FILES],
            "specs_jsonl": rel(SPECS_JSONL),
        },
        "metrics": {
            "bundle_rows": len(bundle_rows),
            "support_rows": len(support_rows),
            "candidate_rows": len(candidate_rows),
            "by_language": {
                language: sum(1 for row in bundle_rows if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in bundle_rows})
            },
            "by_repo_family": {
                repo: sum(1 for row in bundle_rows if str(row.get("repo_family") or "") == repo)
                for repo in sorted({str(row.get("repo_family") or "") for row in bundle_rows})
            },
        },
        "findings": [
            "MirrorMind, agentkernel C/C++, parametergolf C/C++, and code_assist web are now bundled as concrete multilingual next-root materialization artifacts.",
            "The web lane remains overlap-sensitive and should be treated as control/stress rather than promotable headline evidence until a pure-web selected-test family is materialized.",
            "This bundle is the direct executable follow-through on the stage11027 request queue and can feed the next support-package assembly or candidate-slice audit.",
        ],
        "bundle_index": bundle_index,
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "bundle_rows_jsonl": rel(COMBINED_ROWS),
            "support_rows_jsonl": rel(SUPPORT_ROWS),
            "candidate_rows_jsonl": rel(CANDIDATE_ROWS),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(SPECS_JSONL, specs)
    write_jsonl(COMBINED_ROWS, bundle_rows)
    write_jsonl(SUPPORT_ROWS, support_rows)
    write_jsonl(CANDIDATE_ROWS, candidate_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
