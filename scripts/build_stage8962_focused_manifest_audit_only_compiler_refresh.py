#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.dataset_junk_ood_ranker_v1 import read_jsonl
    from scripts.manifest_path_validator import validate_manifest_input_path
    from scripts.software_maintenance_curriculum_cli import compile_contract_rows
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from dataset_junk_ood_ranker_v1 import read_jsonl  # type: ignore
    from manifest_path_validator import validate_manifest_input_path  # type: ignore
    from software_maintenance_curriculum_cli import compile_contract_rows  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8962
NAME = "stage8962_focused_manifest_audit_only_compiler_refresh"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FOCUSED_MANIFEST_AUDIT_ONLY_COMPILER_REFRESH_STAGE8962.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_CARD = OUT_DIR / "focused_manifest_audit_only_compiler_refresh.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8961_repo_local_manifest_inventory_no_mining.json"
MANIFEST = ROOT / "runs/local/manifests/stage8937_tiny_explicit_manifest.jsonl"

EXPECTED_OUTPUTS = [
    "normalized_input_rows.jsonl",
    "judged_rows.jsonl",
    "ranked_rows.jsonl",
    "shortcut_baseline_card.json",
    "counterfactual_obligation_card.json",
    "compile_card.json",
    "dataset_patch_queue.jsonl",
    "compiler_audit_card.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_refresh(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    path_card = validate_manifest_input_path(MANIFEST, must_exist=True)
    rows = read_jsonl(MANIFEST) if path_card["allowed"] else []
    compiler_out = OUT_DIR / "compiler_outputs"
    audit_card = compile_contract_rows(
        rows,
        output_dir=compiler_out,
        decoder_token_cap=768,
        shortcut_ceiling=0.8,
        require_recovered_gates=True,
    ) if rows else {}
    output_status = {name: (compiler_out / name).exists() for name in EXPECTED_OUTPUTS}
    objective_dir = compiler_out / "objective_manifests"
    objective_files = sorted(path.name for path in objective_dir.glob("*.jsonl")) if objective_dir.exists() else []
    checks = {
        "source_stage8961_passed": source.get("passed") is True,
        "manifest_path_allowed": path_card["allowed"] is True,
        "manifest_under_focused_root": path_card.get("root_label") == "runs/local/manifests",
        "manifest_rows_present": len(rows) == 3,
        "manifest_authority_closed": all(not any((row.get("authority") or {}).values()) for row in rows),
        "required_outputs_written": all(output_status.values()),
        "objective_manifest_written": len(objective_files) >= 1,
        "decoder_ce_loss_rows_zero": audit_card.get("decoder_ce_loss_rows") == 0,
        "denoise_ce_loss_rows_zero": audit_card.get("denoise_ce_loss_rows") == 0,
        "runtime_reward_rows_zero": audit_card.get("runtime_reward_rows") == 0,
        "patch_queue_emitted": (compiler_out / "dataset_patch_queue.jsonl").exists(),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8961": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8961,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "FOCUSED_MANIFEST_AUDIT_ONLY_COMPILER_REFRESH",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "path_card": path_card,
        "output_status": output_status,
        "objective_files": objective_files,
        "checks": checks,
        "metrics": {
            "manifest_rows": len(rows),
            "output_files_expected": len(EXPECTED_OUTPUTS),
            "output_files_written": sum(1 for value in output_status.values() if value),
            "objective_files": len(objective_files),
            "decoder_ce_loss_rows": int(audit_card.get("decoder_ce_loss_rows", 0) or 0),
            "denoise_ce_loss_rows": int(audit_card.get("denoise_ce_loss_rows", 0) or 0),
            "runtime_reward_rows": int(audit_card.get("runtime_reward_rows", 0) or 0),
            "patch_queue_rows": int(audit_card.get("patch_queue_rows", 0) or 0),
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
        "decision": "Focused repo-local manifest audit-only compiler refresh completed. The compiler emitted audit outputs and route artifacts, while decoder CE, denoise CE, runtime reward, model execution, mining, and training stayed closed.",
    }


def validate_refresh(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8961, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized", "arxiv_read_authorized_for_compiler", "arxiv_write_authorized"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["decoder_ce_loss_rows", "denoise_ce_loss_rows", "runtime_reward_rows"]:
        if card["metrics"].get(key) != 0:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_refresh(registry)
    failures = validate_refresh(card, registry)
    AUDIT_CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"audit_card": str(AUDIT_CARD.relative_to(ROOT)), "compiler_outputs": str((OUT_DIR / "compiler_outputs").relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Review focused manifest audit outputs and decide whether more no-execution manifest audits are needed. Do not mine /arxiv or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8962 Focused Manifest Audit-Only Compiler Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage runs the recovered compiler wrapper logic against the only focused repo-local manifest discovered by Stage8961. It is audit-only and opens no training or execution.",
        "",
        f"Manifest rows: `{card['metrics']['manifest_rows']}`",
        f"Output files written: `{card['metrics']['output_files_written']}`",
        f"Decoder CE loss rows: `{card['metrics']['decoder_ce_loss_rows']}`",
        f"Denoise CE loss rows: `{card['metrics']['denoise_ce_loss_rows']}`",
        f"Runtime reward rows: `{card['metrics']['runtime_reward_rows']}`",
        "",
        "No mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training is authorized.",
        "",
    ]), encoding="utf-8")
    rows_registry = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows_registry.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows_registry = sorted(rows_registry, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows_registry
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows_registry),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8962 Focused Manifest Audit-Only Compiler Refresh"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8962 audits the focused repo-local Stage8937 manifest through the recovered compiler path. It emits audit outputs and keeps mining, model execution, decoder CE, denoise CE, runtime, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
