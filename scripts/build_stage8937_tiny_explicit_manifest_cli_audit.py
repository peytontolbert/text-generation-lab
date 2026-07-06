#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.manifest_path_validator import validate_manifest_input_path
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from manifest_path_validator import validate_manifest_input_path  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8937
NAME = "stage8937_tiny_explicit_manifest_cli_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TINY_EXPLICIT_MANIFEST_CLI_AUDIT_STAGE8937.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "tiny_explicit_manifest_cli_audit.json"
COMPILER_OUT = OUT_DIR / "compiler_output"
MANIFEST = ROOT / "runs/local/manifests/stage8937_tiny_explicit_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8936_cli_manifest_path_validator_wiring.json"
CLI = ROOT / "scripts/software_maintenance_curriculum_cli.py"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def tiny_rows() -> list[dict[str, Any]]:
    gate_status = {
        "source_inventory_lineage": True,
        "source_provenance": True,
        "contamination_leakage_detector": True,
        "golden_locked_eval_suite": True,
        "drift_canary_regression_monitor": True,
        "cluster_slice_near_duplicate_detector": True,
        "dataset_junk_ood_ranker_v1": True,
        "schema_drift_detector": True,
    }
    return [
        {
            "row_id": "stage8937_pos",
            "objective_family": "tiny_explicit_manifest_audit",
            "semantic_key": "stage8937_group",
            "obligation_type": "POSITIVE_ORIGINAL",
            "split": "train",
            "encoder": "explicit bounded structured evidence",
            "target": "select safe structured action",
            "decode_allowed": False,
            "decoder_budget_ok": True,
            "gate_status": gate_status,
            "authority": dict(AUTHORITY_CLOSED),
        },
        {
            "row_id": "stage8937_retrieve",
            "objective_family": "tiny_explicit_manifest_audit",
            "semantic_key": "stage8937_group",
            "obligation_type": "EVIDENCE_REMOVED_OR_RETRIEVE",
            "split": "eval",
            "encoder": "evidence removed from explicit bounded state",
            "target": "retrieve more",
            "missing_evidence": True,
            "evidence_state": "missing",
            "decode_allowed": False,
            "decoder_budget_ok": True,
            "gate_status": gate_status,
            "authority": dict(AUTHORITY_CLOSED),
        },
        {
            "row_id": "stage8937_boundary",
            "objective_family": "tiny_explicit_manifest_audit",
            "semantic_key": "stage8937_group",
            "obligation_type": "CONTRASTIVE_BOUNDARY_SIBLING",
            "split": "strict_eval",
            "encoder": "long output requested from explicit bounded state",
            "target": "x " * 900,
            "decode_allowed": True,
            "decoder_budget_ok": False,
            "gate_status": gate_status,
            "authority": dict(AUTHORITY_CLOSED),
        },
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def cli_command() -> list[str]:
    return [
        sys.executable,
        str(CLI),
        "--output-dir",
        str(COMPILER_OUT),
        "--mode",
        "manifest_no_mining_audit_only",
        "--input",
        str(MANIFEST),
        "--no-decoder-ce",
        "--no-denoise-ce",
        "--no-runtime",
        "--no-mining",
        "--no-model-execution",
    ]


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST, tiny_rows())
    path_card = validate_manifest_input_path(MANIFEST, must_exist=True)
    result = subprocess.run(cli_command(), cwd=ROOT, text=True, capture_output=True, check=False)
    stdout_card: dict[str, Any] = {}
    if result.returncode == 0 and result.stdout.strip():
        stdout_card = json.loads(result.stdout)
    output_files = sorted(path.name for path in COMPILER_OUT.glob("*")) if COMPILER_OUT.exists() else []
    checks = {
        "source_stage8936_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "manifest_path_validator_passed": path_card["allowed"] is True,
        "manifest_under_allowed_root": path_card.get("root_label") == "runs/local/manifests",
        "cli_returncode_zero": result.returncode == 0,
        "cli_rows_three": stdout_card.get("rows") == 3,
        "cli_training_closed": stdout_card.get("training_authorized") is False,
        "cli_mining_closed": stdout_card.get("data_mining_authorized") is False,
        "cli_decoder_loss_closed": stdout_card.get("decoder_ce_loss_rows") == 0,
        "cli_denoise_loss_closed": stdout_card.get("denoise_ce_loss_rows") == 0,
        "cli_runtime_loss_closed": stdout_card.get("runtime_reward_rows") == 0,
        "compiler_audit_card_written": (COMPILER_OUT / "compiler_audit_card.json").exists(),
        "compile_card_written": (COMPILER_OUT / "compile_card.json").exists(),
        "normalized_rows_written": (COMPILER_OUT / "normalized_input_rows.jsonl").exists(),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TINY_EXPLICIT_MANIFEST_CLI_AUDIT_ONLY",
        "manifest_path_card": path_card,
        "cli_returncode": result.returncode,
        "cli_stdout_card": stdout_card,
        "cli_stderr": result.stderr,
        "output_files": output_files,
        "checks": checks,
        "metrics": {
            "manifest_rows": len(tiny_rows()),
            "output_files": len(output_files),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Tiny explicit repo-local manifest passed the no-mining compiler CLI audit path. This validates path guard wiring and compiler audit outputs only; it opens no mining/training/runtime/model authority.",
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in audit["checks"].items() if value is not True]
    if any((audit.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8936, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry)
    failures = validate_audit(audit, registry)
    CARD.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **audit["metrics"],
        },
        "artifacts": {
            "audit": str(CARD.relative_to(ROOT)),
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "compiler_output": str(COMPILER_OUT.relative_to(ROOT)),
        },
        "decision": audit["decision"],
        "next_best_step": "Return to checkpoint blockers: metadata-only conversion preflight and checkpoint materialization guards. Do not train or mine.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8937 Tiny Explicit Manifest CLI Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "A tiny explicit JSONL manifest under `runs/local/manifests` was passed through the no-mining CLI audit path. The run wrote compiler audit artifacts only and kept mining, training, runtime, model execution, decoder CE, denoise CE, checkpoint, source/body, Gemma, harness, scoring, controller merge, and promotion authority closed.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": summary["next_best_step"]})
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
    marker = "## Stage8937 Tiny Explicit Manifest CLI Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8937 validates the guarded `manifest_no_mining_audit_only` path end to end on a tiny explicit repo-local manifest. It writes audit artifacts only and opens no mining, training, runtime, model execution, decoder, denoise, checkpoint, or promotion authority.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
