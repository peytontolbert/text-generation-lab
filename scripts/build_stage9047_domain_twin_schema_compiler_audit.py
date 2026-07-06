#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES, LOSS_KEYS
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES, LOSS_KEYS  # type: ignore
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9047
NAME = "stage9047_domain_twin_schema_compiler_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9046 = ROOT / "runs/summaries/stage9046_domain_twin_manifest_schema_design.json"
SCHEMA_9046 = ROOT / "runs/local/artifacts/stage9046_domain_twin_manifest_schema_design/domain_twin_manifest_schema_v1.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DOMAIN_TWIN_SCHEMA_COMPILER_AUDIT_STAGE9047.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "domain_twin_schema_compiler_audit.json"

COMPILER_ROW_REQUIRED_FIELDS = [
    "row_id",
    "split",
    "route",
    "semantic_key",
    "gate_status",
    "authority",
    "loss_mask",
    "anti_cheat",
    "provenance",
]
ADAPTER_REQUIRED_OUTPUTS = [
    "domain_twin_judged_rows.jsonl",
    "domain_twin_gate_status_card.json",
    "domain_twin_loss_mask_card.json",
    "domain_twin_shortcut_audit.json",
    "domain_twin_compiler_audit_card.json",
]
ADAPTER_REQUIRED_RULES = [
    "source_metadata_records_must_not_be_compiler_rows_directly",
    "adapter_must_assign_objective_aware_route",
    "adapter_must_emit_complete_gate_status",
    "adapter_must_emit_all_losses_disabled_by_default",
    "adapter_must_emit_semantic_key_without_body_text",
    "adapter_must_preserve_authority_closed",
    "adapter_must_run_shortcut_baselines_before_training",
]
FORBIDDEN_NOW = [
    "compile_domain_twin_records_now",
    "materialize_adapter_outputs_now",
    "enable_any_domain_twin_loss_now",
    "scan_arxiv_now",
    "scan_repository_library_now",
    "read_bodies_now",
    "run_model_now",
    "train_now",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9046 = load_json(SOURCE_9046)
    schema = load_json(SCHEMA_9046)
    family_checks = {
        name: {
            "has_authority": "authority" in spec.get("required_fields", []),
            "has_provenance": "provenance" in spec.get("required_fields", []),
            "has_anti_cheat": "anti_cheat" in spec.get("required_fields", []),
            "forbids_raw_payloads": any("raw" in item or "body" in item for item in spec.get("forbidden_fields", [])),
        }
        for name, spec in schema.items()
    }
    checks = {
        "source_stage9046_present": SOURCE_9046.exists(),
        "source_stage9046_passed": s9046.get("passed") is True,
        "schema_artifact_present": SCHEMA_9046.exists(),
        "schema_families_present": len(schema) == 4,
        "all_schema_families_have_metadata_guards": all(all(values.values()) for values in family_checks.values()),
        "compiler_required_fields_recorded": len(COMPILER_ROW_REQUIRED_FIELDS) >= 9,
        "adapter_required_outputs_recorded": len(ADAPTER_REQUIRED_OUTPUTS) >= 5,
        "adapter_required_rules_recorded": len(ADAPTER_REQUIRED_RULES) >= 7,
        "gate_references_available": len(REQUIRED_RECOVERED_GATE_REFERENCES) >= 8,
        "loss_keys_available": "decoder_ce" in LOSS_KEYS and "denoise_ce" in LOSS_KEYS and "runtime_reward" in LOSS_KEYS,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "DOMAIN_TWIN_SCHEMA_COMPILER_AUDIT_NO_ADAPTER_EXECUTION",
        "family_checks": family_checks,
        "compiler_row_required_fields": COMPILER_ROW_REQUIRED_FIELDS,
        "adapter_required_outputs": ADAPTER_REQUIRED_OUTPUTS,
        "adapter_required_rules": ADAPTER_REQUIRED_RULES,
        "required_recovered_gate_references": list(REQUIRED_RECOVERED_GATE_REFERENCES),
        "loss_keys": list(LOSS_KEYS),
        "forbidden_now": FORBIDDEN_NOW,
        "checks": checks,
        "metrics": {
            "schema_families": len(schema),
            "compiler_row_required_fields": len(COMPILER_ROW_REQUIRED_FIELDS),
            "adapter_required_outputs": len(ADAPTER_REQUIRED_OUTPUTS),
            "adapter_required_rules": len(ADAPTER_REQUIRED_RULES),
            "schema_audit_only": True,
            "domain_twin_records_compiled_now": False,
            "adapter_outputs_materialized_now": False,
            "domain_twin_losses_enabled_now": False,
            "arxiv_scan_authorized_now": False,
            "repository_library_scan_authorized_now": False,
            "body_read_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Domain/Twin metadata records are not compiler rows. A future adapter must judge, route, gate, loss-mask, and shortcut-audit them before any objective manifest can exist.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "domain_twin_records_compiled_now",
        "adapter_outputs_materialized_now",
        "domain_twin_losses_enabled_now",
        "arxiv_scan_authorized_now",
        "repository_library_scan_authorized_now",
        "body_read_authorized_now",
        "training_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"audit": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Design a synthetic fixture-only Domain/Twin adapter validator that emits compiler-shaped rows with closed loss masks and complete gate_status; do not materialize real records.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9047 Domain/Twin Schema Compiler Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Domain/Twin metadata records are source metadata, not direct compiler rows.",
        "A future adapter must add route, semantic key, gate status, authority, anti-cheat, provenance, and loss masks before compiler use.",
        "This stage emits no adapter output and opens no mining/training authority.",
        "",
        "Required adapter outputs:",
        "",
        *[f"- `{item}`" for item in ADAPTER_REQUIRED_OUTPUTS],
        "",
        "Adapter rules:",
        "",
        *[f"- `{item}`" for item in ADAPTER_REQUIRED_RULES],
        "",
        f"Next: {summary['next_best_step']}",
        "",
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
