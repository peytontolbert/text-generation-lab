#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.metadata_only_path_inventory import inventory_paths
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from metadata_only_path_inventory import inventory_paths  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9149
NAME = "stage9149_metadata_only_inventory_runner_dry_run"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9148 = ROOT / "runs/summaries/stage9148_metadata_only_repo_local_path_inventory_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_INVENTORY_RUNNER_DRY_RUN_STAGE9149.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DRY_RUN = OUT_DIR / "metadata_only_inventory_runner_dry_run.json"

SYNTHETIC_PATHS = [
    Path("runs/local/artifacts/stage9000/objective_rows.jsonl"),
    Path("runs/local/artifacts/stage9000/judged_rows.jsonl"),
    Path("runs/local/artifacts/stage9000/junk_ranked_rows.jsonl"),
    Path("runs/local/artifacts/stage9000/shortcut_baseline_card.json"),
    Path("runs/local/artifacts/stage9000/counterfactual_obligation_card.json"),
    Path("runs/local/artifacts/stage9000/source_lineage_card.json"),
    Path("/arxiv/datasets/forbidden/objective_rows.jsonl"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_dry_run(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9148)
    rows = inventory_paths(SYNTHETIC_PATHS, repo_root=ROOT)
    allowed_rows = [row for row in rows if row["path_allowed"] is True]
    blocked_rows = [row for row in rows if row["path_allowed"] is False]
    candidate_types = {str(row["candidate_type"]) for row in rows}
    checks = {
        "source_stage9148_passed": source.get("passed") is True,
        "synthetic_paths_only": True,
        "expected_candidate_types_detected": len(candidate_types) >= 6,
        "forbidden_arxiv_path_blocked": any("/arxiv/" in str(row["path"]) and row["path_allowed"] is False for row in blocked_rows),
        "all_rows_content_unread": all(row["content_read"] is False for row in rows),
        "all_rows_counts_unread": all(row["row_count_read"] is False for row in rows),
        "registry_frontier_stage9148": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9148,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "METADATA_ONLY_INVENTORY_RUNNER_DRY_RUN_SYNTHETIC_PATHS_ONLY",
        "inventory_rows": rows,
        "checks": checks,
        "metrics": {
            "synthetic_paths": len(SYNTHETIC_PATHS),
            "inventory_rows": len(rows),
            "allowed_rows": len(allowed_rows),
            "blocked_rows": len(blocked_rows),
            "candidate_types": len(candidate_types),
            "runner_implemented": True,
            "dry_run_executed_on_synthetic_paths": True,
            "real_inventory_executed": False,
            "path_inventory_materialized": False,
            "file_content_read": False,
            "json_parsed": False,
            "jsonl_rows_counted": False,
            "dataset_rows_loaded": False,
            "arxiv_accessed": False,
            "ticket_instance_materialized": False,
            "real_input_authorized_now": False,
            "real_judge_rows_used": 0,
            "real_ranker_rows_used": 0,
            "real_route_cards_materialized": 0,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "repository_source_bodies_loaded": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Implemented metadata-only inventory runner and exercised it only on synthetic path names. It did not execute over repo artifacts, read file contents, parse JSON, count JSONL rows, access /arxiv, create a ticket instance, materialize route cards, or open training/runtime.",
    }


def validate_dry_run(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9148, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for row in card.get("inventory_rows", []):
        if row.get("content_read") is not False:
            failures.append("content_read")
        if row.get("row_count_read") is not False:
            failures.append("row_count_read")
    for key in [
        "real_inventory_executed",
        "path_inventory_materialized",
        "file_content_read",
        "json_parsed",
        "jsonl_rows_counted",
        "dataset_rows_loaded",
        "arxiv_accessed",
        "ticket_instance_materialized",
        "real_input_authorized_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "repository_source_bodies_loaded",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["real_judge_rows_used", "real_ranker_rows_used", "real_route_cards_materialized"]:
        if card["metrics"].get(key) != 0:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_dry_run(registry)
    failures = validate_dry_run(card, registry)
    public_card = dict(card)
    public_card["failures"] = failures
    public_card["passed"] = not failures
    DRY_RUN.write_text(json.dumps(public_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"dry_run": str(DRY_RUN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Metadata-only inventory runner dry-run failed.",
        "next_best_step": "Audit metadata-only inventory runner dry-run before authorizing any repo-local path inventory execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9149 Metadata-Only Inventory Runner Dry Run",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Implemented the runner and exercised it only on synthetic path names.",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
