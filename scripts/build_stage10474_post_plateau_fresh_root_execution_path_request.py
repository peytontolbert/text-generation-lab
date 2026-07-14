#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10474
NAME = "stage10474_post_plateau_fresh_root_execution_path_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "post_plateau_fresh_root_execution_path_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

AUDIT_JSON = ROOT / "runs/local/artifacts/stage10471_fresh_residual_root_probe_audit/fresh_residual_root_probe_audit.json"
PYTHON_REQUEST = ROOT / "runs/local/artifacts/stage10472_python_verifier_fresh_root_materialization_request/python_verifier_fresh_root_materialization_request.json"
RUST_REQUEST = ROOT / "runs/local/artifacts/stage10473_rust_citation_fresh_root_materialization_request/rust_citation_fresh_root_materialization_request.json"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    python_request = load_json(PYTHON_REQUEST)
    rust_request = load_json(RUST_REQUEST)
    gate = load_json(PROMOTION_GATE)

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "post_plateau_fresh_root_execution_path_defined",
        "claim_scope": [
            "Define the first executable path after the stage10471 plateau without returning to another tiny support finetune loop.",
            "Bind the next training/eval work to fresh-root materialization, root-disjoint packaging, and a stricter promotion gate.",
        ],
        "plateau_summary": {
            "strict_accuracy_before": audit["accuracy"]["baseline"],
            "strict_accuracy_after_probe": audit["accuracy"]["probe"],
            "changed_rows": audit["changed_rows"],
            "regressions": audit["regressions"],
            "conclusion": "support_reweighting_plateau",
        },
        "execution_path": [
            {
                "order": 1,
                "stage_name": "stage10475_python_verifier_materialized_root_bundle_builder",
                "goal": "materialize at least 6 new root-disjoint Python verifier roots from the requested code_assist-style supply",
                "must_satisfy": python_request["materialization_requirements"]["must_include_per_root"],
            },
            {
                "order": 2,
                "stage_name": "stage10476_rust_citation_materialized_root_bundle_builder",
                "goal": "materialize at least 6 new non-tokenizers Rust citation roots with explicit E-vs-F evidence contrast",
                "must_satisfy": rust_request["materialization_requirements"]["must_include_per_root"],
            },
            {
                "order": 3,
                "stage_name": "stage10477_post_plateau_fresh_root_support_package",
                "goal": "package the new Python and Rust roots into a root-disjoint train support manifest with metadata gates",
                "must_satisfy": [
                    "no same-surface strict row copied into train",
                    "repo_family and root_id recorded for every row",
                    "selected_test_anchor_present and verifier_anchor_present recorded for every row",
                    "diagnostic-only support clearly separated from promotable support",
                ],
            },
            {
                "order": 4,
                "stage_name": "stage10478_post_plateau_fresh_root_probe_request",
                "goal": "run one promotable probe against the repaired v2.7 strict overlay plus fresh-root holdout checks",
                "must_satisfy": gate["required_for_future_promotion"],
            },
        ],
        "promotion_gate": {
            "criteria": gate["criteria"],
            "required_for_future_promotion": gate["required_for_future_promotion"],
        },
        "forbidden_shortcuts": [
            "no more claim upgrades from same-surface residual replay",
            "no reuse of the current MirrorMind strict root in train",
            "no tokenizers strict-row copy into train",
            "no counting candle-core diagnostic support as fresh-root evidence",
        ],
        "source_artifacts": {
            "fresh_probe_audit": display(AUDIT_JSON),
            "python_materialization_request": display(PYTHON_REQUEST),
            "rust_materialization_request": display(RUST_REQUEST),
            "residual_promotion_gate": display(PROMOTION_GATE),
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
