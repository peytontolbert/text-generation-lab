#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10473
NAME = "stage10473_rust_citation_fresh_root_materialization_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "rust_citation_fresh_root_materialization_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

AUDIT_JSON = ROOT / "runs/local/artifacts/stage10471_fresh_residual_root_probe_audit/fresh_residual_root_probe_audit.json"
ATLAS_JSON = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json"
BUILDER_JSON = ROOT / "runs/local/artifacts/stage10467_rust_citation_fresh_root_builder/rust_citation_fresh_root_builder.json"
TARGETS_JSONL = ROOT / "runs/local/artifacts/stage10467_rust_citation_fresh_root_builder/rust_citation_fresh_root_targets.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    audit = load_json(AUDIT_JSON)
    atlas = load_json(ATLAS_JSON)
    builder = load_json(BUILDER_JSON)
    targets = load_jsonl(TARGETS_JSONL)

    fresh_targets = [
        row for row in targets
        if row.get("support_role") == "fresh_root_builder_target"
    ]
    diagnostic_targets = [
        row for row in targets
        if row.get("support_role") == "diagnostic_train_support_only"
    ]

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rust_fresh_root_materialization_required",
        "claim_scope": [
            "Translate the stage10471 plateau into a concrete Rust evidence-citation fresh-root materialization request.",
            "Move the Rust residual path away from tokenizers and candle-core same-surface support toward new non-tokenizers roots with explicit evidence contrast.",
        ],
        "plateau_evidence": {
            "baseline_accuracy": audit["accuracy"]["baseline"],
            "probe_accuracy": audit["accuracy"]["probe"],
            "changed_rows": audit["changed_rows"],
            "rust_residual_fixed": audit["headline"]["rust_residual_fixed"],
            "row_id": audit["rust_residual"]["row_id"],
            "predicted": audit["rust_residual"]["probe_label"],
            "target": audit["rust_residual"]["target"],
        },
        "residual_family": {
            "name": "evidence_citation_semantic_contrast",
            "required_skill": "symptom_or_call_path_analogue should beat verifier_and_test_constraint when candidate_change_surface is a tempting negative",
            "failure_mode": "current model stays on the wrong semantic attractor instead of following the stronger supporting evidence type",
        },
        "candidate_supply": {
            "atlas_metrics": atlas["metrics"],
            "fresh_root_targets": fresh_targets,
            "diagnostic_only_targets": diagnostic_targets,
        },
        "materialization_requirements": {
            "minimum_new_roots": 6,
            "must_build_from_non_tokenizers_families": True,
            "preferred_repo_family_order": [
                "linux::rust",
                "candle::candle-datasets",
                "candle::candle-transformers",
                "candle::candle-wasm-examples",
            ],
            "must_include_per_root": [
                "both symptom_or_call_path_analogue and verifier_and_test_constraint as visible options",
                "candidate_change_surface present as a tempting negative but not the gold",
                "real source-backed spans that make the E-vs-F distinction non-trivial",
                "selected-test or verifier-anchor presence recorded explicitly",
            ],
            "anti_cheat_gates": [
                "no direct copying of the tokenizers strict row into train",
                "option-value permutations must vary so E/F identity is not fixed",
                "candle-core support remains diagnostic-only and cannot count toward the fresh-root minimum",
                "future strict roots must remain root-disjoint from any builder support",
            ],
            "promotion_boundary": [
                "fresh non-tokenizers roots are required for a promotable Rust residual fix claim",
                "tokenizers same-surface rows remain diagnostic only",
                "abstention-heavy candle-flash-attn remains useful for honesty training but not as the core citation disambiguation repair path",
            ],
        },
        "recommended_next_stage_names": [
            "stage10474_post_plateau_fresh_root_execution_path_request",
            "stage10476_rust_citation_materialized_root_bundle_builder",
        ],
        "source_artifacts": {
            "fresh_probe_audit": display(AUDIT_JSON),
            "fresh_rust_disjoint_root_atlas": display(ATLAS_JSON),
            "rust_builder": display(BUILDER_JSON),
            "rust_builder_targets": display(TARGETS_JSONL),
        },
    }

    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": request["decision"],
            "request": display(REQUEST_JSON),
        },
    )
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
