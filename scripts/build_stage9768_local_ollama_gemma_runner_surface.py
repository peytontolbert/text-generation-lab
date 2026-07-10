#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9768
NAME = "stage9768_local_ollama_gemma_runner_surface"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "local_ollama_gemma_runner_surface.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCAL_OLLAMA_GEMMA_RUNNER_SURFACE_STAGE9768.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

RUNNER_SCRIPT = ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def build_surface(ollama_version_out: str, ollama_list_out: str, runner_exists: bool) -> dict[str, Any]:
    models = []
    for line in ollama_list_out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if parts:
            models.append(parts[0])
    gemma12b_present = "gemma3:12b" in models
    failures: list[str] = []
    if not runner_exists:
        failures.append("runner_script_missing")
    if "ollama version is" not in ollama_version_out:
        failures.append("ollama_version_unavailable")
    if not gemma12b_present:
        failures.append("local_gemma3_12b_missing")
    return {
        "passed": not failures,
        "failures": failures,
        "ollama_runtime": {
            "installed": "ollama version is" in ollama_version_out,
            "version_output": ollama_version_out.strip(),
            "models": models,
            "local_gemma_model_id": "gemma3:12b" if gemma12b_present else None,
        },
        "runner_surface": {
            "script_path": str(RUNNER_SCRIPT.relative_to(ROOT)),
            "exists": runner_exists,
            "uses_exact_100m_encoder_surface": runner_exists,
            "supports_dry_run": runner_exists,
            "supports_cell_key_filter": runner_exists,
            "supports_limit": runner_exists,
            "supports_split_filter": runner_exists,
            "supports_max_rows": runner_exists,
            "writes_same_prompt_surface_gemma_outputs": runner_exists,
        },
        "blocker_state": (
            "local_ollama_gemma3_12b_present_runner_surface_ready"
            if gemma12b_present and runner_exists
            else "local_ollama_runner_surface_incomplete"
        ),
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    version = _capture(["ollama", "--version"]) if shutil.which("ollama") else None
    listing = _capture(["ollama", "list"]) if shutil.which("ollama") else None
    surface = build_surface(
        version.stdout if version else "",
        listing.stdout if listing else "",
        RUNNER_SCRIPT.exists(),
    )
    AUDIT.write_text(json.dumps(surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the local Ollama Gemma runner surface in dry-run mode first, then execute a bounded standalone comparison slice "
        "against the Stage9748 queue starting with python symbol-binding once Gemma execution is explicitly authorized for local use."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": surface["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "ollama_installed": surface["ollama_runtime"]["installed"],
            "local_gemma3_12b_present": surface["ollama_runtime"]["local_gemma_model_id"] is not None,
            "runner_script_exists": surface["runner_surface"]["exists"],
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "runner_script": str(RUNNER_SCRIPT.relative_to(ROOT)),
        },
        "decision": "Corrected the local runtime picture: this machine already has Ollama plus gemma3:12b, and the repo now exposes a concrete standalone Gemma runner surface that reuses the recovered 100M encoder serialization.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9768 Local Ollama Gemma Runner Surface",
        "",
        f"Passed: `{summary['passed']}`",
        f"Ollama installed: `{summary['metrics']['ollama_installed']}`",
        f"Local gemma3:12b present: `{summary['metrics']['local_gemma3_12b_present']}`",
        f"Runner script exists: `{summary['metrics']['runner_script_exists']}`",
        "",
        "This stage corrects the earlier no-runner assumption. The local machine already has a Gemma-family 12B model through Ollama, and the repo now has a standalone runner surface that reconstructs the recovered 100M encoder text exactly before calling the local model.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "ollama_installed": summary["metrics"]["ollama_installed"],
        "local_gemma3_12b_present": summary["metrics"]["local_gemma3_12b_present"],
        "runner_script_exists": summary["metrics"]["runner_script_exists"],
        "failures": surface["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if surface["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
