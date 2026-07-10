#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10036
NAME = "stage10036_real_fresh_heldout_merge_validator"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "real_fresh_heldout_merge_validator.json"
MERGED = OUT_DIR / "expanded_source_heldout_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_FRESH_HELDOUT_MERGE_VALIDATOR_STAGE10036.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10003_deduped_source_heldout_successor_request/edit_localization_manifest.jsonl"
CANDIDATE_ROWS = ROOT / "runs/local/artifacts/stage10035_real_fresh_heldout_candidate_packet/real_fresh_heldout_candidate_rows.jsonl"
REQUEST = ROOT / "runs/local/artifacts/stage10030_python_cpp_fresh_root_replenishment_request/python_cpp_fresh_root_replenishment_request.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "row_id",
    "source_row_id",
    "split",
    "language_family",
    "objective_family",
    "route",
    "authority",
    "loss_mask",
    "gate_status",
    "source_backed",
    "source_stage",
    "source_row_ref",
    "semantic_key",
    "source_lineage",
    "graph_input",
    "query",
    "corrupted_state",
    "input_state",
    "clean_state",
    "target",
    "anti_cheat",
    "counterfactual_root_row_id",
    "counterfactual_role",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


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
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _contains_fill_me(value: Any) -> bool:
    if isinstance(value, str):
        return "FILL_ME" in value
    if isinstance(value, dict):
        return any(_contains_fill_me(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_fill_me(v) for v in value)
    return False


def _request_counts(request: dict[str, Any]) -> dict[str, int]:
    rows = request.get("requests") if isinstance(request.get("requests"), list) else []
    counts: dict[str, int] = {}
    for row in rows:
        key = f"{row.get('language_family')}:{row.get('target_label')}"
        counts[key] = int(row.get("requested_fresh_independent_roots") or 0)
    return counts


def build_audit() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    candidate_rows = load_jsonl(CANDIDATE_ROWS)
    request = load_json(REQUEST)
    requested_counts = _request_counts(request)
    base_row_ids = {str(row.get("row_id") or "") for row in base_rows}
    base_source_ids = {str(row.get("source_row_id") or "") for row in base_rows if row.get("source_row_id")}
    base_root_ids = {str(row.get("counterfactual_root_row_id") or "") for row in base_rows}

    failures: list[str] = []
    per_row_failures: dict[str, list[str]] = {}
    valid_rows: list[dict[str, Any]] = []

    for row in candidate_rows:
        row_id = str(row.get("row_id") or "")
        row_failures: list[str] = []
        missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(row.keys()))
        if missing:
            row_failures.append("missing_required_top_level_keys")
        if _contains_fill_me(row):
            row_failures.append("contains_fill_me_placeholder")
        if row_id in base_row_ids:
            row_failures.append("row_id_already_in_base_manifest")

        source_row_id = str(row.get("source_row_id") or "")
        if not source_row_id:
            row_failures.append("missing_source_row_id")
        elif source_row_id in base_source_ids:
            row_failures.append("source_row_id_already_in_base_manifest")

        split = str(row.get("split") or "")
        if split not in {"eval", "strict_eval"}:
            row_failures.append("split_not_heldout_eval")

        anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        if anti_cheat.get("requires_fresh_source_root") is not True:
            row_failures.append("requires_fresh_source_root_not_true")
        if anti_cheat.get("requires_expert_maintainer_review_before_promotion") is not True:
            row_failures.append("requires_expert_review_not_true")
        if anti_cheat.get("target_label_literals_in_prompt_surface") is not False:
            row_failures.append("target_label_literals_in_prompt_surface_not_false")

        source_lineage = row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}
        if source_lineage.get("locked_eval_source") is not True:
            row_failures.append("locked_eval_source_not_true")
        if source_lineage.get("train_eligible_lineage") is not False:
            row_failures.append("train_eligible_lineage_not_false")

        gate_status = row.get("gate_status") if isinstance(row.get("gate_status"), dict) else {}
        if gate_status.get("golden_locked_eval_suite") is not True:
            row_failures.append("golden_locked_eval_suite_not_true")
        if gate_status.get("source_inventory_lineage") is not True:
            row_failures.append("source_inventory_lineage_not_true")
        if gate_status.get("source_provenance") is not True:
            row_failures.append("source_provenance_not_true")

        clean_state = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        if str(target.get("edit_localization") or "") != str(clean_state.get("edit_localization") or ""):
            row_failures.append("target_edit_localization_mismatch")

        root_id = str(row.get("counterfactual_root_row_id") or "")
        if root_id in base_root_ids:
            row_failures.append("counterfactual_root_already_in_base_manifest")

        if row_failures:
            per_row_failures[row_id] = row_failures
        else:
            valid_rows.append(row)

    actual_counts = Counter(f"{row.get('language_family')}:{row.get('target', {}).get('edit_localization')}" for row in valid_rows)
    if dict(actual_counts) != requested_counts:
        failures.append("request_coverage_mismatch")
    if len(valid_rows) != len(candidate_rows):
        failures.append("candidate_rows_failed_validation")

    merged_rows = [*base_rows, *valid_rows]
    write_jsonl(MERGED, merged_rows)
    metrics = {
        "base_rows": len(base_rows),
        "candidate_rows": len(candidate_rows),
        "valid_candidate_rows": len(valid_rows),
        "merged_rows": len(merged_rows),
        "candidate_language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in candidate_rows).items())),
        "merged_language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in merged_rows).items())),
        "requested_counts": dict(sorted(requested_counts.items())),
        "actual_valid_counts": dict(sorted(actual_counts.items())),
        "failing_candidate_rows": len(per_row_failures),
    }
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "per_row_failures": per_row_failures,
        "merge_output": display(MERGED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the expanded source-heldout manifest for the next same-manifest 100M-versus-Gemma rerun, and require expert-maintainer plus anti-cheat review before promoting any of these fresh heldout rows into a headline benchmark claim."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"audit": display(AUDIT), "merged_manifest": display(MERGED), "doc": display(DOC)},
        "decision": "Validated the real stage10035 fresh heldout candidate rows against source independence, heldout-only routing, anti-cheat requirements, and replenishment request coverage, then merged them with the deduped source-heldout manifest for the next honest comparison rerun.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10036 Real Fresh Heldout Merge Validator",
                "",
                f"Passed: `{summary['passed']}`",
                f"Merged rows: `{built['metrics']['merged_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
