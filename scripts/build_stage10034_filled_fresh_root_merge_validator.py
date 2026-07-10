#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10034
NAME = "stage10034_filled_fresh_root_merge_validator"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "filled_fresh_root_merge_validator.json"
MERGED = OUT_DIR / "candidate_expanded_source_heldout_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FILLED_FRESH_ROOT_MERGE_VALIDATOR_STAGE10034.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10003_deduped_source_heldout_successor_request/edit_localization_manifest.jsonl"
SCAFFOLD_ROWS = ROOT / "runs/local/artifacts/stage10033_python_cpp_fresh_root_scaffold_packet/python_cpp_fresh_root_scaffold_rows.jsonl"

REQUIRED_TOP_LEVEL_KEYS = {
    "row_id",
    "split",
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


def build_audit() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    scaffold_rows = load_jsonl(SCAFFOLD_ROWS)
    base_row_ids = {str(row.get("row_id") or "") for row in base_rows}
    base_root_ids = {str(row.get("counterfactual_root_row_id") or "") for row in base_rows}
    failures: list[str] = []
    per_row_failures: dict[str, list[str]] = {}
    valid_rows: list[dict[str, Any]] = []

    for row in scaffold_rows:
        row_id = str(row.get("row_id") or "")
        row_failures: list[str] = []
        missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(row.keys()))
        if missing:
            row_failures.append("missing_required_top_level_keys")
        if _contains_fill_me(row):
            row_failures.append("contains_fill_me_placeholder")
        if row_id in base_row_ids:
            row_failures.append("row_id_already_in_base_manifest")
        split = str(row.get("split") or "")
        if split not in {"eval", "strict_eval"}:
            row_failures.append("split_not_heldout_eval")
        root_id = str(row.get("counterfactual_root_row_id") or "")
        if root_id in base_root_ids:
            row_failures.append("counterfactual_root_already_in_base_manifest")
        anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        if anti_cheat.get("requires_fresh_source_root") is not True:
            row_failures.append("requires_fresh_source_root_not_true")
        if anti_cheat.get("requires_expert_maintainer_review_before_promotion") is not True:
            row_failures.append("requires_expert_review_not_true")
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        if not target.get("edit_localization"):
            row_failures.append("missing_edit_localization_target")
        if row_failures:
            per_row_failures[row_id] = row_failures
        else:
            valid_rows.append(row)

    merged_rows = [*base_rows, *valid_rows]
    write_jsonl(MERGED, merged_rows)
    metrics = {
        "base_rows": len(base_rows),
        "candidate_rows": len(scaffold_rows),
        "valid_candidate_rows": len(valid_rows),
        "merged_rows": len(merged_rows),
        "candidate_language_counts": dict(sorted(Counter(str(row.get("corrupted_state", {}).get("language") or "") for row in scaffold_rows).items())),
        "valid_candidate_language_counts": dict(sorted(Counter(str(row.get("corrupted_state", {}).get("language") or "") for row in valid_rows).items())),
        "failing_candidate_rows": len(per_row_failures),
    }
    if per_row_failures:
        failures.append("candidate_rows_still_fail_validation")
    if valid_rows:
        failures.append("filled_scaffold_rows_present_but_should_still_be_placeholders_until_populated")
    audit = {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "per_row_failures": per_row_failures,
        "merge_output": display(MERGED),
    }
    return audit


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Fill the stage10033 scaffold rows with real fresh independent heldout roots until this validator reports zero placeholders and zero source collisions, then use the merged manifest for the next honest comparison rerun."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"audit": display(AUDIT), "merged_manifest": display(MERGED), "doc": display(DOC)},
        "decision": "Materialized a strict validation-and-merge gate for filled fresh-root scaffold rows so future heldout expansion can only proceed after placeholders are removed, source independence is maintained, and anti-cheat requirements remain intact.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10034 Filled Fresh Root Merge Validator",
                "",
                f"Passed: `{summary['passed']}`",
                f"Failing candidate rows: `{built['metrics']['failing_candidate_rows']}`",
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


if __name__ == "__main__":
    main()
