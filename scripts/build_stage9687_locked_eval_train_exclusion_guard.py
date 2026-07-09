#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from curriculum_compiler import compile_rows, write_jsonl
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from golden_locked_eval_suite import load_locked_source_ids_from_exclusions
except ModuleNotFoundError:
    from scripts.curriculum_compiler import compile_rows, write_jsonl  # type: ignore
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.golden_locked_eval_suite import load_locked_source_ids_from_exclusions  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9687
NAME = "stage9687_locked_eval_train_exclusion_guard"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9686_golden_locked_eval_suite_validation.json"
SOURCE_EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
FIXTURE = OUT_DIR / "locked_eval_train_exclusion_negative_fixture.jsonl"
COMPILED_DIR = OUT_DIR / "compiled_fixture"
AUDIT = OUT_DIR / "locked_eval_train_exclusion_guard_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_LOCKED_EVAL_TRAIN_EXCLUSION_GUARD_STAGE9687.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = load_json(SOURCE_SUMMARY)
    locked_ids = sorted(load_locked_source_ids_from_exclusions(SOURCE_EXCLUSIONS))
    if not locked_ids:
        raise SystemExit("no locked source IDs found")
    locked_direct = locked_ids[0]
    locked_nested = locked_ids[1]
    rows = [
        {
            "row_id": "locked_direct_decoder_ce_candidate",
            "split": "train",
            "route": "KEEP_BOUNDED_DECODER",
            "source_id": locked_direct,
        },
        {
            "row_id": "locked_nested_lineage_decoder_ce_candidate",
            "split": "train",
            "route": "KEEP_BOUNDED_DECODER",
            "source_lineage": {"graph_nodes_source_id": locked_nested, "graph_spans_source_id": "open_fixture_source"},
        },
        {
            "row_id": "locked_split_role_structured_candidate",
            "split": "train",
            "split_role": "locked_regression",
            "route": "KEEP_STRUCTURED",
            "source_id": "open_fixture_source",
        },
        {
            "row_id": "open_decoder_ce_candidate",
            "split": "train",
            "route": "KEEP_BOUNDED_DECODER",
            "source_id": "open_fixture_source",
        },
    ]
    write_jsonl(FIXTURE, rows)
    buckets, card = compile_rows(
        rows,
        allow_decoder=True,
        allow_denoise=True,
        allow_runtime=False,
        require_recovered_gates=False,
        locked_source_ids=set(locked_ids),
    )
    for objective, objective_rows in buckets.items():
        write_jsonl(COMPILED_DIR / f"{objective}.jsonl", objective_rows)
    (COMPILED_DIR / "compile_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    human_rows = buckets.get("human_review", [])
    decoder_rows = buckets.get("bounded_decoder_ce", [])
    blocked_row_ids = {row.get("row_id") for row in human_rows}
    decoder_row_ids = {row.get("row_id") for row in decoder_rows}
    blocked_with_forbidden_loss = [
        row.get("row_id")
        for row in human_rows
        if (row.get("loss_mask") or {}).get("decoder_ce") or (row.get("loss_mask") or {}).get("denoise_ce") or (row.get("loss_mask") or {}).get("runtime_reward")
    ]
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("stage9686_not_passed")
    if card.get("locked_source_exclusion_rows") != 3:
        failures.append("locked_source_exclusion_rows_not_3")
    if card.get("loss_counts", {}).get("decoder_ce") != 1:
        failures.append("decoder_ce_not_limited_to_open_row")
    if "open_decoder_ce_candidate" not in decoder_row_ids or len(decoder_row_ids) != 1:
        failures.append("open_decoder_row_not_only_decoder_candidate")
    for expected in ["locked_direct_decoder_ce_candidate", "locked_nested_lineage_decoder_ce_candidate", "locked_split_role_structured_candidate"]:
        if expected not in blocked_row_ids:
            failures.append(f"missing_blocked_row:{expected}")
    if blocked_with_forbidden_loss:
        failures.append("blocked_rows_have_forbidden_loss")
    authority_rows = [row.get("row_id") for bucket in buckets.values() for row in bucket if any((row.get("authority") or {}).values())]
    if authority_rows:
        failures.append("authority_rows_present")

    audit = {
        "passed": not failures,
        "failures": failures,
        "fixture_rows": len(rows),
        "locked_source_ids_loaded": len(locked_ids),
        "locked_source_exclusion_rows": card.get("locked_source_exclusion_rows"),
        "decoder_ce_loss_rows": card.get("loss_counts", {}).get("decoder_ce", 0),
        "denoise_ce_loss_rows": card.get("loss_counts", {}).get("denoise_ce", 0),
        "runtime_reward_loss_rows": card.get("loss_counts", {}).get("runtime_reward", 0),
        "human_review_rows": len(human_rows),
        "decoder_rows": len(decoder_rows),
        "blocked_row_ids": sorted(blocked_row_ids),
        "decoder_row_ids": sorted(decoder_row_ids),
        "blocked_with_forbidden_loss": blocked_with_forbidden_loss,
        "authority_rows": authority_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = "Build Stage9688 locked-eval guard graph attachment and then resume non-eval training package selection with locked-source exclusions required."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "compiled_dir": str(COMPILED_DIR.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "fixture": str(FIXTURE.relative_to(ROOT)),
        },
        "decision": "Added and validated a compiler-level locked eval source exclusion guard with a no-training negative fixture.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9687 Locked Eval Train Exclusion Guard",
        "",
        f"Passed: `{summary['passed']}`",
        f"Fixture rows: `{audit['fixture_rows']}`",
        f"Locked source IDs loaded: `{audit['locked_source_ids_loaded']}`",
        f"Locked exclusion rows: `{audit['locked_source_exclusion_rows']}`",
        f"Decoder CE rows after guard: `{audit['decoder_ce_loss_rows']}`",
        f"Blocked rows with forbidden loss: `{audit['blocked_with_forbidden_loss']}`",
        "",
        "The negative fixture proves direct locked source IDs, nested source lineage IDs, and locked split roles are forced to human review before loss masks can authorize training.",
        "",
        "No Gemma, harness, runtime, model execution, scoring, source/body emission, training, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": failures,
        "locked_source_exclusion_rows": audit["locked_source_exclusion_rows"],
        "decoder_ce_loss_rows": audit["decoder_ce_loss_rows"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
