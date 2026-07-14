#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10708
NAME = "stage10708_rewritten_support_execution_contract_repair"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "rewritten_support_execution_contract_repair.json"
TRAIN_ROWS_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "validation_rows.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_PACKAGE = ROOT / "runs/local/artifacts/stage10704_rewritten_multilingual_support_package/rewritten_multilingual_support_package.json"
SOURCE_TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10704_rewritten_multilingual_support_package/train_rows.jsonl"
SOURCE_VALIDATION_ROWS = ROOT / "runs/local/artifacts/stage10704_rewritten_multilingual_support_package/validation_rows.jsonl"


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def repaired_row(row: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(row))
    gold = str(copied.get("gold_option_label") or copied.get("decoder_text") or copied.get("target_text") or "")
    if gold:
        copied["decoder_text"] = gold
        copied["target_text"] = gold
    copied["loss_mask"] = {
        "action_sequence_ce": False,
        "allowed_import_policy_ce": False,
        "blocked_import_policy_ce": False,
        "build_mode_ce": False,
        "decoder_ce": True,
        "denoise_ce": False,
        "edit_localization_ce": False,
        "episode_boundary_match_ce": False,
        "episode_failure_type_ce": False,
        "episode_repair_outcome_ce": False,
        "episode_step_value_mse": False,
        "episode_target_prefix_match_ce": False,
        "file_plan_ce": False,
        "patch_operator_ce": False,
        "repair_surface_ce": False,
        "repo_dependency_policy_ce": False,
        "runtime_reward": False,
        "suffix_choice_ce": False,
        "surface_role_ce": False,
        "symbol_binding_ce": False,
        "verifier_repair_ce": False,
    }
    copied["execution_contract_repaired"] = True
    copied["execution_contract_repair_stage"] = STAGE
    return copied


def main() -> None:
    source_package = load_json(SOURCE_PACKAGE)
    train_rows = [repaired_row(row) for row in load_jsonl(SOURCE_TRAIN_ROWS)]
    validation_rows = [repaired_row(row) for row in load_jsonl(SOURCE_VALIDATION_ROWS)]

    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, validation_rows)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rewritten_support_execution_contract_repaired",
        "claim_scope": [
            "Repair the rewritten support rows so they satisfy the bounded probe execution contract.",
            "Populate decoder/target text from the resolved gold option and enable a minimal decoder loss mask.",
            "Do not change eval or strict frontier rows in this repair stage.",
        ],
        "source_artifacts": {
            "rewritten_support_package": display(SOURCE_PACKAGE),
            "source_train_rows": display(SOURCE_TRAIN_ROWS),
            "source_validation_rows": display(SOURCE_VALIDATION_ROWS),
        },
        "counts": {
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "rows_with_decoder_text_after_repair": sum(1 for row in train_rows + validation_rows if str(row.get("decoder_text") or "")),
            "rows_with_loss_mask_after_repair": sum(1 for row in train_rows + validation_rows if row.get("loss_mask")),
        },
        "headline_findings": [
            "The rewritten support rows were structurally admitted but not executable because decoder targets and enabled losses were missing.",
            "This repair keeps the rewritten semantics unchanged while making the rows compatible with the bounded decoder probe contract.",
            "The honest eval/strict frontier remains untouched; only rewritten support rows are altered here.",
        ],
        "recommended_next_stage": "stage10709_rewritten_plus_reviewed_probe_request_execution_repaired",
        "outputs": {
            "train_rows": display(TRAIN_ROWS_JSONL),
            "validation_rows": display(VALIDATION_ROWS_JSONL),
            "summary_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "summary_json": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
