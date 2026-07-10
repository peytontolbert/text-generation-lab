#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10042
NAME = "stage10042_expanded_source_heldout_review_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "expanded_source_heldout_review_packet.json"
ROWS = OUT_DIR / "expanded_source_heldout_review_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EXPANDED_SOURCE_HELDOUT_REVIEW_PACKET_STAGE10042.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10036_real_fresh_heldout_merge_validator/expanded_source_heldout_manifest.jsonl"

REVIEW_FOCUS = [
    "Verify that each fresh heldout row has exactly one justified edit-localization answer from visible evidence.",
    "Check whether any field ordering, choice wording, or row metadata leaks the answer label despite source-heldout isolation.",
    "Confirm these fresh rows remain heldout-only and should not be replayed into train before the next same-manifest comparison.",
    "Mark rows that should be converted to abstain, rebuilt, or excluded if expert maintainers judge them underdetermined.",
]


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


def build_packet() -> dict[str, Any]:
    manifest = load_jsonl(MANIFEST)
    fresh_rows = [
        row for row in manifest
        if str(row.get("locked_guard_refresh_stage") or "") == "stage10035_real_fresh_heldout_candidate_packet"
    ]
    review_rows: list[dict[str, Any]] = []
    language_counts = Counter()
    label_counts = Counter()
    split_counts = Counter()
    for row in fresh_rows:
        language = str(row.get("language_family") or "")
        label = str((row.get("target") or {}).get("edit_localization") or "")
        split = str(row.get("split") or "")
        language_counts[language] += 1
        label_counts[f"{language}:{label}"] += 1
        split_counts[split] += 1
        review_rows.append(
            {
                "row_id": row.get("row_id"),
                "source_row_id": row.get("source_row_id"),
                "language_family": language,
                "split": split,
                "expected_label": label,
                "hidden_target_family": (row.get("clean_state") or {}).get("edit_localization_target_hidden"),
                "counterfactual_root_row_id": row.get("counterfactual_root_row_id"),
                "counterfactual_role": row.get("counterfactual_role"),
                "visible_evidence": {
                    "task_observation": (row.get("input_state") or {}).get("task_observation"),
                    "visible_locality_evidence": (row.get("input_state") or {}).get("visible_locality_evidence"),
                    "file_extension": (row.get("input_state") or {}).get("file_extension"),
                    "context_config_visible": (row.get("input_state") or {}).get("context_config_visible"),
                    "context_entrypoint_visible": (row.get("input_state") or {}).get("context_entrypoint_visible"),
                    "context_symbol_names_visible": (row.get("input_state") or {}).get("context_symbol_names_visible"),
                    "context_tests_visible": (row.get("input_state") or {}).get("context_tests_visible"),
                },
                "anti_cheat_flags": {
                    "requires_fresh_source_root": (row.get("anti_cheat") or {}).get("requires_fresh_source_root"),
                    "requires_expert_maintainer_review_before_promotion": (row.get("anti_cheat") or {}).get("requires_expert_maintainer_review_before_promotion"),
                    "target_label_literals_in_prompt_surface": (row.get("anti_cheat") or {}).get("target_label_literals_in_prompt_surface"),
                    "locked_eval_source": (row.get("source_lineage") or {}).get("locked_eval_source"),
                    "train_eligible_lineage": (row.get("source_lineage") or {}).get("train_eligible_lineage"),
                },
                "required_checks": list(REVIEW_FOCUS),
            }
        )

    failures: list[str] = []
    if len(review_rows) != 18:
        failures.append("fresh_review_rows_not_18")
    if language_counts.get("python") != 6:
        failures.append("python_review_rows_not_6")
    if language_counts.get("c_cpp") != 12:
        failures.append("c_cpp_review_rows_not_12")
    if split_counts != Counter({"eval": 18}):
        failures.append("fresh_review_splits_not_all_eval")

    write_jsonl(ROWS, review_rows)
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "rows": len(review_rows),
            "language_counts": dict(sorted(language_counts.items())),
            "split_counts": dict(sorted(split_counts.items())),
            "label_counts": dict(sorted(label_counts.items())),
            "required_checks_per_row": len(REVIEW_FOCUS),
        },
        "review_focus": list(REVIEW_FOCUS),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    PACKET.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use this packet during expert-maintainer and anti-cheat review of the 18 fresh heldout Python/C++ rows before promoting any expanded same-manifest comparison result."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packet": display(PACKET), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Materialized the review packet for the 18 fresh expanded source-heldout Python/C++ rows so expert-maintainer and anti-cheat review can proceed on the exact new heldout evidence rather than the older smaller baseline.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10042 Expanded Source Heldout Review Packet",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{built['metrics']['rows']}`",
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
