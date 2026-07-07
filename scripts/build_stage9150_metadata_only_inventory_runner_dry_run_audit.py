#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9149_metadata_only_inventory_runner_dry_run import build_dry_run, validate_dry_run
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9149_metadata_only_inventory_runner_dry_run import build_dry_run, validate_dry_run  # type: ignore
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9150
NAME = "stage9150_metadata_only_inventory_runner_dry_run_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9149 = ROOT / "runs/summaries/stage9149_metadata_only_inventory_runner_dry_run.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_INVENTORY_RUNNER_DRY_RUN_AUDIT_STAGE9150.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "metadata_only_inventory_runner_dry_run_audit.json"

NEGATIVE_CASES = [
    "source_stage_missing",
    "not_synthetic_paths_only",
    "arxiv_not_blocked",
    "row_content_read",
    "row_count_read",
    "real_inventory_executed",
    "path_inventory_materialized",
    "file_content_read",
    "json_parsed",
    "jsonl_rows_counted",
    "dataset_rows_loaded",
    "arxiv_accessed",
    "ticket_instance_materialized",
    "route_cards_materialized",
    "loss_masks_materialized",
    "training_authorized",
    "runtime_authorized",
    "authority_open",
    "bad_registry_frontier",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9149) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_dry_run(registry(latest=9148))
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage_missing":
            candidate["checks"]["source_stage9148_passed"] = False
        elif name == "not_synthetic_paths_only":
            candidate["checks"]["synthetic_paths_only"] = False
        elif name == "arxiv_not_blocked":
            candidate["checks"]["forbidden_arxiv_path_blocked"] = False
        elif name == "row_content_read":
            candidate["inventory_rows"][0]["content_read"] = True
        elif name == "row_count_read":
            candidate["inventory_rows"][0]["row_count_read"] = True
        elif name == "real_inventory_executed":
            candidate["metrics"]["real_inventory_executed"] = True
        elif name == "path_inventory_materialized":
            candidate["metrics"]["path_inventory_materialized"] = True
        elif name == "file_content_read":
            candidate["metrics"]["file_content_read"] = True
        elif name == "json_parsed":
            candidate["metrics"]["json_parsed"] = True
        elif name == "jsonl_rows_counted":
            candidate["metrics"]["jsonl_rows_counted"] = True
        elif name == "dataset_rows_loaded":
            candidate["metrics"]["dataset_rows_loaded"] = True
        elif name == "arxiv_accessed":
            candidate["metrics"]["arxiv_accessed"] = True
        elif name == "ticket_instance_materialized":
            candidate["metrics"]["ticket_instance_materialized"] = True
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "runtime_authorized":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_dry_run(candidate, registry(latest=9999) if name == "bad_registry_frontier" else registry(latest=9148))
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9149)
    dry_run_registry = registry(latest=9148)
    base = build_dry_run(dry_run_registry)
    base_failures = validate_dry_run(base, dry_run_registry)
    negatives = run_negative_cases()
    checks = {
        "source_stage9149_passed": source.get("passed") is True,
        "base_dry_run_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "synthetic_paths_only": base["checks"]["synthetic_paths_only"] is True,
        "forbidden_arxiv_path_blocked": base["checks"]["forbidden_arxiv_path_blocked"] is True,
        "all_rows_content_unread": base["checks"]["all_rows_content_unread"] is True,
        "all_rows_counts_unread": base["checks"]["all_rows_counts_unread"] is True,
        "real_inventory_not_executed": base["metrics"]["real_inventory_executed"] is False,
        "inventory_not_materialized": base["metrics"]["path_inventory_materialized"] is False,
        "authority_closed": not any(base["authority"].values()),
        "registry_frontier_stage9149": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9149,
        "authority_counts_zero": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    failures.extend(base_failures)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_failures": base_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "dry_run_audited": True,
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
        "decision": "Audited metadata-only inventory runner dry-run and rejected mutations that would execute a real inventory, materialize inventory output, read files, parse JSON, count rows, access /arxiv, create tickets, materialize route/loss cards, or open training/runtime.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry_json)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Metadata-only inventory runner dry-run audit failed.",
        "next_best_step": "Design explicit repo-local inventory execution authorization; do not execute inventory yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9150 Metadata-Only Inventory Runner Dry-Run Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
