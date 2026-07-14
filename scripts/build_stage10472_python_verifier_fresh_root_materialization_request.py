#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10472
NAME = "stage10472_python_verifier_fresh_root_materialization_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "python_verifier_fresh_root_materialization_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

AUDIT_JSON = ROOT / "runs/local/artifacts/stage10471_fresh_residual_root_probe_audit/fresh_residual_root_probe_audit.json"
ATLAS_JSON = ROOT / "runs/local/artifacts/stage10445_python_disjoint_root_candidate_atlas/python_disjoint_root_candidate_atlas.json"
BUILDER_JSON = ROOT / "runs/local/artifacts/stage10466_python_verifier_fresh_root_builder/python_verifier_fresh_root_builder.json"
TARGETS_JSONL = ROOT / "runs/local/artifacts/stage10466_python_verifier_fresh_root_builder/python_verifier_fresh_root_targets.jsonl"


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

    promotable_targets = [
        row for row in targets
        if row.get("support_role") == "promotable_disjoint_support_candidate"
    ]
    honesty_targets = [
        row for row in targets
        if row.get("support_role") == "abstention_honesty_support_only"
    ]

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_fresh_root_materialization_required",
        "claim_scope": [
            "Translate the stage10471 plateau into a concrete Python verifier fresh-root materialization request.",
            "Forbid more same-surface or tiny support-only finetunes as the main fix path for the MirrorMind verifier residual.",
        ],
        "plateau_evidence": {
            "baseline_accuracy": audit["accuracy"]["baseline"],
            "probe_accuracy": audit["accuracy"]["probe"],
            "changed_rows": audit["changed_rows"],
            "python_residual_fixed": audit["headline"]["python_residual_fixed"],
            "row_id": audit["python_residual"]["row_id"],
            "predicted": audit["python_residual"]["probe_label"],
            "target": audit["python_residual"]["target"],
        },
        "residual_family": {
            "name": "verifier_target_disambiguation",
            "required_skill": "multiple plausible tests are visible, but only one verifier target should move",
            "failure_mode": "current model stays on the wrong sibling verifier target instead of the gold verifier target",
        },
        "candidate_supply": {
            "atlas_summary": atlas["summary"],
            "promotable_disjoint_targets": promotable_targets,
            "honesty_only_targets": honesty_targets,
        },
        "materialization_requirements": {
            "minimum_new_roots": 6,
            "must_build_from_root_disjoint_families": True,
            "preferred_repo_family_order": [
                "code_assist",
                "additional fresh repo families beyond code_assist if available",
            ],
            "must_include_per_root": [
                "at least three candidate tests or verifier targets",
                "one close sibling wrong test target that stays tempting under the visible evidence",
                "selected-test anchor present but not answer-revealing by name alone",
                "visible evidence that distinguishes the gold verifier target from the wrong sibling target",
            ],
            "anti_cheat_gates": [
                "test names alone must not solve the row without the evidence block",
                "candidate ordering must not reveal the verifier target",
                "no reuse of the current MirrorMind strict root in train support",
                "any future strict root from the same family must remain root-disjoint from support material",
            ],
            "promotion_boundary": [
                "code_assist support can justify a fresh-support training package",
                "code_assist alone does not justify a broad Python maintainer claim",
                "agentkernel successor rows remain abstention-honesty support only until converted into executable bounded rows",
            ],
        },
        "recommended_next_stage_names": [
            "stage10474_post_plateau_fresh_root_execution_path_request",
            "stage10475_python_verifier_materialized_root_bundle_builder",
        ],
        "source_artifacts": {
            "fresh_probe_audit": display(AUDIT_JSON),
            "python_disjoint_root_atlas": display(ATLAS_JSON),
            "python_builder": display(BUILDER_JSON),
            "python_builder_targets": display(TARGETS_JSONL),
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
