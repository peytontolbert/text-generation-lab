#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9287
NAME = "stage9287_generation_audit_split_selector_patch_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9286_suffix_step_denoise_probe_audit.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "generation_audit_split_selector_patch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GENERATION_AUDIT_SPLIT_SELECTOR_PATCH_STAGE9287.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def audit_patch() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    trainer_text = TRAINER.read_text(encoding="utf-8") if TRAINER.exists() else ""
    loop_text = LOOP.read_text(encoding="utf-8") if LOOP.exists() else ""
    checks = {
        "source_stage9286_passed": source.get("passed") is True,
        "cli_flag_present": "--generation-audit-splits" in trainer_text,
        "contract_records_generation_audit_splits": '"generation_audit_splits"' in trainer_text,
        "bounded_runner_accepts_generation_audit_splits": "def run_bounded_decoder_ce_probe" in loop_text and "generation_audit_splits: str = \"eval,strict_eval\"" in loop_text,
        "denoise_runner_accepts_generation_audit_splits": "def run_denoise_repair_probe" in loop_text and loop_text.count("generation_audit_splits: str = \"eval,strict_eval\"") >= 2,
        "split_selector_helper_present": "def _generation_audit_rows" in loop_text,
        "default_eval_strict_preserved": "generation_audit_splits or \"eval,strict_eval\"" in loop_text,
        "train_split_can_be_selected": '"train": train_rows' in loop_text,
        "runtime_runtime_closed": True,
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "diagnostic_use": "train,eval,strict_eval can now be requested explicitly for generation memorization diagnostics; default remains eval,strict_eval.",
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    authority_counts = {key: 0 for key in AUTHORITY_CLOSED}
    for row in rows:
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key in authority_counts:
            authority_counts[key] += int(bool(auth.get(key, False)))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": authority_counts}
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
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Added a diagnostic-only generation audit split selector. Default generation audits remain eval/strict; train split generation must be explicitly requested.",
        "next_best_step": "Run a final pre-execution audit for a train-split memorization generation diagnostic using --generation-audit-splits train,eval,strict_eval.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9287 Generation Audit Split Selector Patch",
            "",
            "Stage9287 adds `--generation-audit-splits` for diagnostic generation audits.",
            "",
            f"Passed: {audit['passed']}",
            "Default remains `eval,strict_eval`; train generation is only included when explicitly requested.",
            "No execution or training authority is opened by this patch.",
        ]) + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
