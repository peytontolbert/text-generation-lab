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
STAGE = 9076
NAME = "stage9076_future_source_output_ticket_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9059 = ROOT / "runs/summaries/stage9059_long_context_route_card_materialization_audit_contract.json"
SOURCE_9075 = ROOT / "runs/summaries/stage9075_current_frontier_reconciliation_after_trainer_docs_graph.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FUTURE_SOURCE_OUTPUT_TICKET_DESIGN_STAGE9076.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "future_source_output_ticket_design.json"

REQUIRED_TICKET_FIELDS = [
    "ticket_id",
    "ticket_stage",
    "scope",
    "allowed_source_roots",
    "allowed_output_roots",
    "metadata_access_policy",
    "body_access_policy",
    "route_card_policy",
    "index_policy",
    "candidate_policy",
    "arxiv_policy",
    "cleanup_policy",
    "caps",
    "required_preflight_artifacts",
    "required_post_artifacts",
    "forbidden_operations",
    "authority",
]

REQUIRED_PREFLIGHT_ARTIFACTS = [
    "source_output_ticket_authorization_card.json",
    "allowed_roots_inventory.json",
    "no_row_body_read_plan.json",
    "no_destructive_cleanup_plan.json",
    "output_path_policy_card.json",
]

REQUIRED_POST_ARTIFACTS = [
    "source_output_access_audit.json",
    "route_card_materialization_audit.json",
    "path_lineage_card.json",
    "no_body_read_proof.json",
    "no_arxiv_write_without_explicit_backup_ticket.json",
]

FORBIDDEN_OPERATIONS = [
    "READ_ROW_BODY_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "READ_PRIVATE_SESSION_BODY",
    "MATERIALIZE_TRAINING_MANIFEST",
    "RUN_TRAINER_DRY_RUN",
    "START_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "RUN_HARNESS_SCORING",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
    "DELETE_ANY_SOURCE_ROOT",
    "DELETE_ARXIV",
    "WRITE_TO_ARXIV_WITHOUT_BACKUP_TICKET",
    "CLEANUP_OUTSIDE_RUN_ARTIFACT_DIR",
]

TICKET_TEMPLATE = {
    "ticket_id": "future_stage9xxx_source_output_ticket_inactive",
    "ticket_stage": "future_stage9xxx",
    "scope": "metadata_only_source_output_for_long_context_route_cards",
    "allowed_source_roots": [],
    "allowed_output_roots": ["runs/local/artifacts/future_ticket_placeholder"],
    "metadata_access_policy": {
        "list_paths_allowed": False,
        "read_metadata_indexes_allowed": False,
        "read_file_sizes_hashes_allowed": False,
    },
    "body_access_policy": {
        "read_row_bodies": False,
        "read_source_bodies": False,
        "read_decoder_targets": False,
        "read_private_session_bodies": False,
    },
    "route_card_policy": {
        "materialize_route_cards": False,
        "requires_stage9059_audit": True,
        "compiler_ready_default": False,
        "training_ready_default": False,
    },
    "index_policy": {
        "build_index_now": False,
        "candidate_mining_now": False,
        "compound_only_optional_future_flag": True,
    },
    "candidate_policy": {
        "candidate_rows_materialized_now": 0,
        "requires_dispersion_guard": True,
        "requires_compound_candidate_guard": True,
        "requires_junk_ood_route": True,
        "requires_loss_mask_translation": True,
    },
    "arxiv_policy": {
        "arxiv_read_authorized_now": False,
        "arxiv_write_authorized_now": False,
        "never_delete_arxiv": True,
        "arxiv_is_backup_root": True,
        "write_requires_separate_backup_ticket": True,
    },
    "cleanup_policy": {
        "cleanup_authorized_now": False,
        "must_use_safe_cleanup_only": True,
        "forbid_root_cleanup": True,
        "forbid_arxiv_cleanup": True,
    },
    "caps": {
        "max_metadata_paths_future": 0,
        "max_route_cards_future": 0,
        "max_candidate_rows_future": 0,
        "max_output_bytes_future": 0,
    },
    "required_preflight_artifacts": REQUIRED_PREFLIGHT_ARTIFACTS,
    "required_post_artifacts": REQUIRED_POST_ARTIFACTS,
    "forbidden_operations": FORBIDDEN_OPERATIONS,
    "authority": dict(AUTHORITY_CLOSED),
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    s9059 = load_json(SOURCE_9059)
    s9075 = load_json(SOURCE_9075)
    checks = {
        "source_stage9059_present": SOURCE_9059.exists(),
        "source_stage9059_passed": s9059.get("passed") is True,
        "source_stage9075_present": SOURCE_9075.exists(),
        "source_stage9075_passed": s9075.get("passed") is True,
        "required_ticket_fields_recorded": len(REQUIRED_TICKET_FIELDS) >= 17,
        "preflight_artifacts_recorded": len(REQUIRED_PREFLIGHT_ARTIFACTS) >= 5,
        "post_artifacts_recorded": len(REQUIRED_POST_ARTIFACTS) >= 5,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 16,
        "template_authority_closed": not any(TICKET_TEMPLATE["authority"].values()),
        "template_blocks_body_access": not any(TICKET_TEMPLATE["body_access_policy"].values()),
        "template_blocks_current_arxiv_io": TICKET_TEMPLATE["arxiv_policy"]["arxiv_read_authorized_now"] is False and TICKET_TEMPLATE["arxiv_policy"]["arxiv_write_authorized_now"] is False,
        "template_records_never_delete_arxiv": TICKET_TEMPLATE["arxiv_policy"]["never_delete_arxiv"] is True,
        "template_blocks_cleanup": TICKET_TEMPLATE["cleanup_policy"]["cleanup_authorized_now"] is False,
        "registry_frontier_stage9075": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9075,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "FUTURE_SOURCE_OUTPUT_TICKET_DESIGN_INACTIVE_NO_ACCESS",
        "required_ticket_fields": REQUIRED_TICKET_FIELDS,
        "ticket_template": TICKET_TEMPLATE,
        "checks": checks,
        "metrics": {
            "required_ticket_fields": len(REQUIRED_TICKET_FIELDS),
            "required_preflight_artifacts": len(REQUIRED_PREFLIGHT_ARTIFACTS),
            "required_post_artifacts": len(REQUIRED_POST_ARTIFACTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "index_building_authorized": False,
            "candidate_mining_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
            "trainer_dry_run_executed_now": False,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "model_forward_attempted": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Future source/output ticket schema is defined as inactive. It grants no current source metadata reads, row/source body reads, route-card materialization, indexing, candidate mining, /arxiv IO, cleanup, trainer dry run, model execution, or training.",
    }


def validate_contract(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9075, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    template = card.get("ticket_template") or {}
    for field in REQUIRED_TICKET_FIELDS:
        if field not in template:
            failures.append(f"missing_ticket_field:{field}")
    if any((template.get("authority") or {}).values()):
        failures.append("template_authority_open")
    if not (template.get("arxiv_policy") or {}).get("never_delete_arxiv"):
        failures.append("missing_never_delete_arxiv")
    for key in [
        "ticket_instantiated_now",
        "source_metadata_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "route_cards_materialized_now",
        "index_building_authorized",
        "candidate_mining_authorized",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "cleanup_authorized_now",
        "trainer_dry_run_executed_now",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "model_forward_attempted",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("candidate_rows_materialized") != 0:
        failures.append("candidate_rows_materialized")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_contract(registry)
    failures = validate_contract(card, registry)
    CONTRACT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Future source/output ticket design failed.",
        "next_best_step": "Audit this inactive source/output ticket design, then keep route-card materialization and mining closed until an explicit future ticket is instantiated.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9076 Future Source/Output Ticket Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Defines an inactive future ticket schema for source/output access needed before route-card materialization or long-context candidate work. It grants no current reads, writes, cleanup, mining, trainer execution, model execution, or training.",
        "",
        f"Required ticket fields: `{summary['metrics']['required_ticket_fields']}`",
        f"Forbidden operations: `{summary['metrics']['forbidden_operations']}`",
        f"Never delete `/arxiv`: `{TICKET_TEMPLATE['arxiv_policy']['never_delete_arxiv']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage9076 Future Source/Output Ticket Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9076 defines an inactive future source/output ticket schema for route-card materialization and long-context candidate work. It records allowed future policy fields, forbidden operations, path/output controls, and the permanent rule that `/arxiv` is a backup root and must never be deleted.",
            "",
            "No source metadata read, row/source body read, route-card materialization, index build, candidate mining, /arxiv IO, cleanup, trainer dry run, model forward, decoder CE, denoise CE, runtime, or training is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
