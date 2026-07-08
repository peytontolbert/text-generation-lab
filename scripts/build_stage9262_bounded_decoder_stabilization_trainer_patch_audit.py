#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9262
NAME = "stage9262_bounded_decoder_stabilization_trainer_patch_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9261_bounded_decoder_stabilization_contract.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "bounded_decoder_stabilization_trainer_patch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_STABILIZATION_TRAINER_PATCH_AUDIT_STAGE9262.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_SNIPPETS = {
    "trainer_cli_eos_loss_weight": (TRAINER, "--eos-loss-weight"),
    "trainer_contract_records_eos_weight": (TRAINER, '"eos_loss_weight": args.eos_loss_weight'),
    "bounded_call_passes_eos_weight": (TRAINER, "eos_loss_weight=args.eos_loss_weight"),
    "weighted_eos_loss_helper": (LOOP, "def _decoder_ce_loss("),
    "post_clip_gradient_telemetry": (LOOP, '"post_clip_grad_norm": post_clip_grad_norm'),
    "pre_clip_gradient_telemetry": (LOOP, '"pre_clip_grad_norm": pre_clip_grad_norm'),
    "repetition_negative_artifact": (LOOP, "generated_repetition_negative_rows.jsonl"),
    "eos_length_bucket_audit": (LOOP, '"length_buckets": length_buckets'),
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def audit_patch() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9261_not_passed")
    snippet_results: dict[str, bool] = {}
    for key, (path, snippet) in REQUIRED_SNIPPETS.items():
        present = path.exists() and snippet in path.read_text(encoding="utf-8")
        snippet_results[key] = present
        if not present:
            failures.append(f"missing_snippet:{key}")
    help_result = subprocess.run([sys.executable, str(TRAINER), "--help"], text=True, capture_output=True, check=True)
    help_has_eos = "--eos-loss-weight" in help_result.stdout
    if not help_has_eos:
        failures.append("help_missing_eos_loss_weight")
    compile_result = subprocess.run([sys.executable, "-m", "py_compile", str(TRAINER), str(LOOP)], text=True, capture_output=True)
    if compile_result.returncode != 0:
        failures.append("py_compile_failed")
    forbidden = json.dumps({"trainer": TRAINER.read_text(encoding="utf-8"), "loop": LOOP.read_text(encoding="utf-8")}, sort_keys=True).lower()
    forbidden_runtime_open = any(token in forbidden for token in ["gemma_execution_authorized_next\": true", "runtime_authorized\": true", "checkpoint_export\": true"])
    if forbidden_runtime_open:
        failures.append("forbidden_authority_opening_literal")
    return {
        "passed": not failures,
        "failures": failures,
        "snippet_results": snippet_results,
        "help_has_eos_loss_weight": help_has_eos,
        "py_compile_passed": compile_result.returncode == 0,
        "model_execution_attempted": False,
        "training_attempted": False,
        "runtime_attempted": False,
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_patch()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "required_snippets": len(REQUIRED_SNIPPETS),
            "required_snippets_present": sum(1 for value in audit["snippet_results"].values() if value),
            "help_has_eos_loss_weight": audit["help_has_eos_loss_weight"],
            "py_compile_passed": audit["py_compile_passed"],
            "model_execution_attempted": False,
            "training_attempted": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited the bounded decoder stabilization trainer patch. This stage is static/no-execution; second target-100M execution still requires a fresh contract-only preflight and review.",
        "next_best_step": "Run trellis-focused trainer tests, then build Stage9263 stabilized bounded decoder contract-only preflight with --eos-loss-weight 4.0 and learning-rate 1e-5.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9262 Bounded Decoder Stabilization Trainer Patch Audit",
                "",
                "Static audit for the Stage9261 trainer/runtime requirements.",
                "",
                f"Required snippets present: {summary['metrics']['required_snippets_present']}/{summary['metrics']['required_snippets']}",
                f"Help exposes `--eos-loss-weight`: {audit['help_has_eos_loss_weight']}",
                f"Compile passed: {audit['py_compile_passed']}",
                "",
                "No model execution or training is performed by this audit.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
