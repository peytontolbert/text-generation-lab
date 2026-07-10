#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "runs/local/artifacts/stage9929_weighted_harness_runner_plan/weighted_harness_runner_plan.json"
SUPPORT_MODULES = {
    "golden_locked_eval_suite": ROOT / "scripts/golden_locked_eval_suite.py",
    "traced_eval_observability": ROOT / "scripts/traced_eval_observability.py",
    "patch_minimality_complexity_meter": ROOT / "scripts/patch_minimality_complexity_meter.py",
    "semantic_equivalence_metamorphic_verifier": ROOT / "scripts/semantic_equivalence_metamorphic_verifier.py",
}
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def support_module_status() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "path": display_path(path),
            "present": path.exists(),
        }
        for name, path in SUPPORT_MODULES.items()
    }


def select_cells(plan: dict[str, Any], *, cell_key: str | None) -> list[dict[str, Any]]:
    rows = [row for row in (plan.get("cell_plans") or []) if isinstance(row, dict)]
    if cell_key:
        rows = [row for row in rows if str(row.get("cell_key") or "") == cell_key]
    return rows


def contract_payload(cell: dict[str, Any]) -> dict[str, Any]:
    return {
        "cell_key": cell.get("cell_key"),
        "proxy_standalone_cell_key": cell.get("proxy_standalone_cell_key"),
        "language_family": cell.get("language_family"),
        "skill_area": cell.get("skill_area"),
        "runner_mode": "dry_run_contract_only",
        "executable_now": False,
        "runtime_integration_ready": True,
        "remaining_machine_gap": cell.get("remaining_machine_gap"),
        "remaining_human_gates": list(cell.get("remaining_human_gates") or []),
        "required_artifacts": list(cell.get("required_artifacts") or []),
        "artifact_paths": dict(cell.get("artifact_paths") or {}),
        "runner_steps": list(cell.get("runner_steps") or []),
        "support_modules": support_module_status(),
        "standalone_proxy_frontier": dict(cell.get("standalone_proxy_frontier") or {}),
        "authority": dict(AUTHORITY_CLOSED),
    }


def write_contract(cell: dict[str, Any]) -> Path:
    packet_dir = ROOT / str((cell.get("artifact_paths") or {}).get("packet_dir") or "")
    output = packet_dir / "harness_runtime_contract.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(contract_payload(cell), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize dry-run full-product harness runtime contracts for the weighted proxy frontier.")
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--cell-key", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = load_json(args.plan)
    selected = select_cells(plan, cell_key=args.cell_key)
    outputs = []
    for cell in selected:
        outputs.append(display_path(write_contract(cell)))
    print(json.dumps({
        "plan": display_path(args.plan),
        "cell_key": args.cell_key,
        "selected_cells": [row.get("cell_key") for row in selected],
        "written_contracts": outputs,
        "support_modules": support_module_status(),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
