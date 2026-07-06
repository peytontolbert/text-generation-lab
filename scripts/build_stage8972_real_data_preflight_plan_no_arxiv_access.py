#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8972
NAME = "stage8972_real_data_preflight_plan_no_arxiv_access"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_DATA_PREFLIGHT_PLAN_NO_ARXIV_ACCESS_STAGE8972.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PLAN = OUT_DIR / "real_data_preflight_plan_no_arxiv_access.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8971_trainer_contract_reconciliation_no_execution.json"

PROTECTED_ROOTS = [
    "/arxiv",
    "/arxiv/datasets",
    "/arxiv/repositories",
]

FUTURE_PREFLIGHT_STEPS = [
    "verify_arxiv_roots_exist_metadata_only",
    "inventory_dataset_files_by_name_size_extension_only",
    "inventory_repository_roots_by_name_only",
    "reject_hidden_checkpoint_or_runtime_probe_paths",
    "sample_zero_rows_until_explicit_compiler_ticket",
    "write_all_preflight_outputs_under_runs_local_artifacts_only",
    "require_dataset_judge_route_card_before_mining",
    "require_loss_mask_card_before_training",
    "require_trainer_contract_only_ticket_before_any_output_dir_generation",
]

FORBIDDEN_IN_PREFLIGHT = [
    "read_dataset_rows",
    "read_repository_source_body",
    "write_to_arxiv",
    "delete_or_cleanup_arxiv",
    "load_model_checkpoint",
    "execute_training",
    "execute_runtime",
    "start_mining",
    "upload_to_huggingface",
]

REQUIRED_OUTPUTS_FOR_FUTURE_PREFLIGHT = [
    "arxiv_root_metadata_card.json",
    "dataset_file_inventory_metadata_only.jsonl",
    "repository_root_inventory_metadata_only.jsonl",
    "protected_path_policy_card.json",
    "real_data_preflight_decision_card.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_plan(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    checks = {
        "source_stage8971_passed": source.get("passed") is True,
        "protected_roots_declared": len(PROTECTED_ROOTS) == 3 and "/arxiv" in PROTECTED_ROOTS,
        "future_steps_declared": len(FUTURE_PREFLIGHT_STEPS) >= 8,
        "forbidden_operations_declared": len(FORBIDDEN_IN_PREFLIGHT) >= 8,
        "future_outputs_declared": len(REQUIRED_OUTPUTS_FOR_FUTURE_PREFLIGHT) >= 5,
        "no_arxiv_access_performed": True,
        "no_training_or_mining_authorized": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8971_or_8972": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8971, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REAL_DATA_PREFLIGHT_PLAN_NO_ARXIV_ACCESS",
        "protected_roots": PROTECTED_ROOTS,
        "future_preflight_steps": FUTURE_PREFLIGHT_STEPS,
        "forbidden_in_preflight": FORBIDDEN_IN_PREFLIGHT,
        "required_outputs_for_future_preflight": REQUIRED_OUTPUTS_FOR_FUTURE_PREFLIGHT,
        "checks": checks,
        "metrics": {
            "protected_roots": len(PROTECTED_ROOTS),
            "future_preflight_steps": len(FUTURE_PREFLIGHT_STEPS),
            "forbidden_operations": len(FORBIDDEN_IN_PREFLIGHT),
            "required_future_outputs": len(REQUIRED_OUTPUTS_FOR_FUTURE_PREFLIGHT),
            "arxiv_access_performed": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The real-data preflight is designed but not executed. /arxiv remains protected as backup storage; future preflight may inspect only metadata and must write outputs under runs/local/artifacts, never /arxiv.",
    }


def validate_plan(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8971, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "arxiv_access_performed",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_plan(registry)
    failures = validate_plan(card, registry)
    PLAN.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **card["metrics"],
        },
        "artifacts": {"preflight_plan": str(PLAN.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Implement a metadata-only /arxiv preflight script that cannot read row bodies or source bodies and cannot write outside runs/local/artifacts.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8972 Real Data Preflight Plan No Arxiv Access",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs the future real-data preflight only. It does not access `/arxiv`, load dataset rows, read repository source bodies, mine data, train, execute runtime, or upload anything.",
        "",
        "## Future Metadata-Only Steps",
        "",
        *[f"- `{step}`" for step in FUTURE_PREFLIGHT_STEPS],
        "",
        "## Forbidden",
        "",
        *[f"- `{item}`" for item in FORBIDDEN_IN_PREFLIGHT],
        "",
    ]), encoding="utf-8")
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
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8972 Real Data Preflight Plan No Arxiv Access"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8972 designs the future real-data preflight around /arxiv/datasets and /arxiv/repositories. It performs no /arxiv access and keeps all data, mining, and training authority closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
