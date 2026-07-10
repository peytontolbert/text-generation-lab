#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10117
NAME = "stage10117_true_source_backed_maintainer_eval_replacement_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "true_source_backed_maintainer_eval_replacement_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_MAINTAINER_EVAL_REPLACEMENT_CONTRACT_STAGE10117.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUEST_10099 = ROOT / "runs/local/artifacts/stage10099_true_source_backed_edit_localization_builder_request/true_source_backed_edit_localization_builder_request.json"
INVENTORY_10100 = ROOT / "runs/summaries/stage10100_true_source_backed_multilingual_session_inventory_audit.json"
SUCCESSOR_10110 = ROOT / "docs" / "REAL_SESSION_SHORTCUT_SAFE_SUCCESSOR_PACKET_STAGE10110.md"

PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "patch_impact",
    "verifier_outcome",
    "minimal_fix_selection",
    "regression_risk",
    "abstention_insufficient_evidence",
]


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
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build() -> dict[str, Any]:
    request_10099 = load_json(REQUEST_10099)
    inventory_10100 = load_json(INVENTORY_10100)
    failures: list[str] = []
    if request_10099.get("passed") is not True:
        failures.append("stage10099_not_passed")
    if inventory_10100.get("passed") is not True:
        failures.append("stage10100_not_passed")

    language_counts = ((inventory_10100.get("metrics") or {}).get("aggregate_language_row_counts")) or {}
    rust_rows = int(language_counts.get("rust", 0) or 0)
    if rust_rows != 0:
        failures.append("expected_rust_rows_to_still_be_zero")

    contract = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "stage10099_replacement_request": display(REQUEST_10099),
            "stage10100_inventory_audit": display(INVENTORY_10100),
            "stage10110_successor_doc": display(SUCCESSOR_10110),
        },
        "decision": (
            "Retire the synthetic edit-localization lineage as the main benchmark path and replace it with a true source-backed maintainer eval builder "
            "whose unit of independence is a real bug/fix root case rather than a single compressed classification row."
        ),
        "claim_boundary": {
            "current_shortcut_safe_successor_packet_is_useful_but_not_full_maintainer_eval": True,
            "synthetic_stage8636_to_stage8765_lineage_retired_for_headline_benchmarking": True,
            "new_builder_must_be_root_bundled_and_multi_perspective": True,
            "four_language_maintainer_claim_blocked_by_real_rust_supply": True,
        },
        "root_bundle_contract": {
            "unit_of_independence": "root_bug_fix_case",
            "required_perspectives": PERSPECTIVES,
            "minimum_rows_per_root": 6,
            "target_rows_per_root": "6_to_10",
            "root_level_solved_definition": (
                "A root is only solved when the model is coherent across localization, evidence, alternatives, patch impact, verifier behavior, "
                "minimal-fix judgment, regression risk, and abstention where applicable."
            ),
        },
        "required_visible_evidence": [
            "concrete_failure_text",
            "test_assertion_or_expected_vs_actual",
            "trace_or_call_site_excerpt",
            "candidate_file_or_symbol_paths",
            "real_source_snippet_spans",
            "candidate_patch_or_edit_preview_for_actionable perspectives",
            "abstention_option_when_visible evidence is insufficient",
        ],
        "anti_cheat_and_validity_requirements": [
            "split by root, repo, and source commit rather than by row",
            "never reuse synthetic task_observation or synthetic visible_evidence strings from stage8636 or stage8765",
            "store real source lineage and human-maintainer answer keys per root bundle",
            "add perspective-specific decoys and alternative hypotheses instead of asking the same answer in paraphrases",
            "score both per-perspective accuracy and root-level consistency",
            "require abstention rows where visible evidence is underdetermined",
            "keep candidate order, template signatures, and path hints from becoming stable answer proxies",
        ],
        "builder_bootstrap_plan": {
            "python": "bootstrap_now_from_true_source_backed_session_inventory",
            "c_cpp": "bootstrap_now_from_true_source_backed_session_inventory",
            "web_js_ts_html": "bootstrap_now_from_true_source_backed_session_inventory",
            "rust": "replenish_real_session_roots_before_four_language_claim",
            "inventory_best_starting_point": (inventory_10100.get("metrics") or {}).get("best_bootstrap_inventory"),
        },
        "metrics": {
            "replacement_builder_required": bool((request_10099.get("metrics") or {}).get("replacement_builder_required")),
            "available_true_source_rows_python": int(language_counts.get("python", 0) or 0),
            "available_true_source_rows_c_cpp": int(language_counts.get("c_cpp", 0) or 0),
            "available_true_source_rows_web": int(language_counts.get("web_js_ts_html", 0) or 0),
            "available_true_source_rows_rust": rust_rows,
            "required_perspective_count": len(PERSPECTIVES),
        },
        "next_best_step": (
            "Implement the true source-backed maintainer eval builder on real external graph/session roots for python, c_cpp, and web first, "
            "with root-bundled multi-perspective rows and abstention; replenish real Rust roots in parallel before any four-language maintainer claim."
        ),
        "failures": failures,
    }
    return contract


def write_doc(contract: dict[str, Any]) -> None:
    DOC.write_text(
        "\n".join(
            [
                "# Stage10117 True Source-Backed Maintainer Eval Replacement Contract",
                "",
                f"Passed: `{contract['passed']}`",
                "",
                contract["decision"],
                "",
                "Required perspectives:",
                *[f"- `{name}`" for name in PERSPECTIVES],
                "",
                f"Next: {contract['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    contract = build()
    write_json(CONTRACT, contract)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": contract["passed"],
        "artifacts": contract["artifacts"],
        "metrics": contract["metrics"],
        "decision": contract["decision"],
        "next_best_step": contract["next_best_step"],
    }
    write_json(SUMMARY, summary)
    write_doc(contract)
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": contract["passed"], "failures": contract["failures"], "metrics": contract["metrics"]}, indent=2, sort_keys=True))
    if contract["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
