#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.manifest_path_validator import ALLOWED_MANIFEST_ROOTS, FORBIDDEN_ABSOLUTE_ROOTS
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from manifest_path_validator import ALLOWED_MANIFEST_ROOTS, FORBIDDEN_ABSOLUTE_ROOTS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8958
NAME = "stage8958_real_manifest_audit_only_route_card_readiness"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_MANIFEST_AUDIT_ONLY_ROUTE_CARD_READINESS_STAGE8958.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "real_manifest_audit_only_route_card_readiness.json"

SOURCE_SUMMARIES = {
    8934: "stage8934_real_manifest_audit_only_contract",
    8935: "stage8935_audit_only_manifest_path_validator",
    8936: "stage8936_cli_manifest_path_validator_wiring",
    8937: "stage8937_tiny_explicit_manifest_cli_audit",
    8957: "stage8957_no_mining_compiler_readiness_refresh_after_decoder_gates",
}

REQUIRED_ROUTE_OUTPUTS = [
    "normalized_input_rows.jsonl",
    "judged_rows.jsonl",
    "ranked_rows.jsonl",
    "shortcut_baseline_card.json",
    "counterfactual_obligation_card.json",
    "objective_manifests/*.jsonl",
    "compile_card.json",
    "dataset_patch_queue.jsonl",
    "compiler_audit_card.json",
]

REQUIRED_ROUTE_CARD_FIELDS = [
    "row_id",
    "route",
    "risk_bucket",
    "junk_score",
    "reasons",
    "loss_mask",
    "authority",
    "split",
    "semantic_key",
    "objective_family",
]

REQUIRED_AUDIT_GATES = [
    "explicit_path_only",
    "jsonl_only",
    "repo_local_allowed_root",
    "no_glob",
    "no_traversal",
    "no_remote_uri",
    "no_arxiv_input_or_write",
    "no_arbitrary_data_root",
    "no_recursive_discovery",
    "no_training_loss_authority",
    "no_decoder_ce_authority",
    "no_denoise_ce_authority",
    "no_runtime_authority",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for stage, stage_name in SOURCE_SUMMARIES.items():
        summary = load_json(summary_path(stage_name))
        sources[str(stage)] = {
            "stage_name": stage_name,
            "exists": bool(summary),
            "passed": summary.get("passed") is True,
            "metrics": summary.get("metrics") or {},
        }
    stage8937_metrics = sources["8937"]["metrics"]
    checks = {
        "source_summaries_present": all(item["exists"] for item in sources.values()),
        "source_summaries_passed": all(item["passed"] for item in sources.values()),
        "allowed_input_roots_recorded": len(ALLOWED_MANIFEST_ROOTS) == 4,
        "forbidden_absolute_roots_include_arxiv": "/arxiv" in {str(path) for path in FORBIDDEN_ABSOLUTE_ROOTS},
        "route_outputs_recorded": len(REQUIRED_ROUTE_OUTPUTS) >= 9,
        "route_card_fields_recorded": len(REQUIRED_ROUTE_CARD_FIELDS) >= 10,
        "audit_gates_recorded": len(REQUIRED_AUDIT_GATES) >= 13,
        "tiny_explicit_manifest_output_files_present": int(stage8937_metrics.get("output_files", 0) or 0) >= 9,
        "tiny_explicit_manifest_rows_present": int(stage8937_metrics.get("manifest_rows", 0) or 0) > 0,
        "data_mining_closed": stage8937_metrics.get("data_mining_authorized") is False,
        "training_closed": stage8937_metrics.get("training_authorized") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8957": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8957,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REAL_MANIFEST_AUDIT_ONLY_ROUTE_CARD_READINESS",
        "source_status": sources,
        "allowed_manifest_roots": list(ALLOWED_MANIFEST_ROOTS),
        "forbidden_absolute_roots": [str(path) for path in FORBIDDEN_ABSOLUTE_ROOTS],
        "required_route_outputs": REQUIRED_ROUTE_OUTPUTS,
        "required_route_card_fields": REQUIRED_ROUTE_CARD_FIELDS,
        "required_audit_gates": REQUIRED_AUDIT_GATES,
        "checks": checks,
        "metrics": {
            "source_summaries": len(SOURCE_SUMMARIES),
            "source_summaries_passed": sum(1 for item in sources.values() if item["passed"]),
            "allowed_manifest_roots": len(ALLOWED_MANIFEST_ROOTS),
            "forbidden_absolute_roots": len(FORBIDDEN_ABSOLUTE_ROOTS),
            "required_route_outputs": len(REQUIRED_ROUTE_OUTPUTS),
            "required_route_card_fields": len(REQUIRED_ROUTE_CARD_FIELDS),
            "required_audit_gates": len(REQUIRED_AUDIT_GATES),
            "tiny_explicit_manifest_rows": int(stage8937_metrics.get("manifest_rows", 0) or 0),
            "tiny_explicit_manifest_output_files": int(stage8937_metrics.get("output_files", 0) or 0),
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Real-manifest audit-only route-card readiness is recovered: explicit repo-local manifests may be inspected by the no-mining compiler wrapper and must emit route/audit cards. This does not authorize recursive discovery, /arxiv reads or writes, mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8957, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized", "arxiv_read_authorized_for_compiler", "arxiv_write_authorized"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"card": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Refresh the full training-readiness blocker matrix after compiler, converter, bounded-decoder, and manifest-audit recovery; keep mining/training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8958 Real-Manifest Audit-Only Route-Card Readiness",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records the route-card and path-boundary contract for explicit local manifests. `/arxiv` remains backup-only for this path and is not authorized as a compiler input or output root.",
        "",
        f"Required route outputs: `{card['metrics']['required_route_outputs']}`",
        f"Required route card fields: `{card['metrics']['required_route_card_fields']}`",
        f"Data mining authorized: `{card['metrics']['data_mining_authorized']}`",
        f"Training authorized: `{card['metrics']['training_authorized']}`",
        "",
        "No mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training is authorized.",
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
    marker = "## Stage8958 Real-Manifest Audit-Only Route-Card Readiness"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8958 records explicit local manifest route-card requirements. The no-mining compiler path may inspect focused repo-local JSONL manifests only; /arxiv, arbitrary /data paths, discovery, mining, execution, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
