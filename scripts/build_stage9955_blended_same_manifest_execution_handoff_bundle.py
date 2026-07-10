#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9955
NAME = "stage9955_blended_same_manifest_execution_handoff_bundle"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BUNDLE = OUT_DIR / "blended_same_manifest_execution_handoff_bundle.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_SAME_MANIFEST_EXECUTION_HANDOFF_BUNDLE_STAGE9955.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
CANDIDATE_100M = ROOT / "runs/local/artifacts/stage9949_web_targeted_blended_execution_readiness_gate/first_surface_execution_candidate_edit_localization.json"
GEMMA_QUEUE = ROOT / "runs/local/artifacts/stage9952_blended_edit_localization_gemma_request/blended_edit_localization_gemma_queue.json"
GEMMA_PACKETS = ROOT / "runs/local/artifacts/stage9952_blended_edit_localization_gemma_request/blended_edit_localization_gemma_packets.jsonl"
COMPARE_GATE = ROOT / "runs/local/artifacts/stage9954_blended_edit_localization_same_manifest_comparison_gate/blended_edit_localization_same_manifest_comparison_gate.json"
RUNNER = ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def build_bundle() -> dict[str, Any]:
    candidate_100m = load_json(CANDIDATE_100M)
    gemma_queue = load_json(GEMMA_QUEUE)
    gemma_packets = load_jsonl(GEMMA_PACKETS)
    compare_gate = load_json(COMPARE_GATE)
    failures: list[str] = []

    queue_entries = [row for row in (gemma_queue.get("queue_entries") or []) if isinstance(row, dict)]
    gemma_entry = queue_entries[0] if queue_entries else {}
    gemma_packet = gemma_packets[0] if gemma_packets else {}

    if candidate_100m.get("selected_surface") != "edit_localization":
        failures.append("stage9949_candidate_not_edit_localization")
    if gemma_entry.get("skill_area") != "edit_localization":
        failures.append("stage9952_entry_not_edit_localization")
    if compare_gate.get("passed") is not True:
        failures.append("stage9954_not_passed")

    hundred_m_command = [str(item) for item in (candidate_100m.get("command") or [])]
    gemma_command = [
        "python",
        str(RUNNER.relative_to(ROOT)),
        "--queue",
        str(GEMMA_QUEUE.relative_to(ROOT)),
        "--packets",
        str(GEMMA_PACKETS.relative_to(ROOT)),
        "--model",
        "gemma3:12b",
        "--cell-key",
        str(gemma_entry.get("cell_key") or ""),
    ]

    row_contract = compare_gate.get("row_contract") if isinstance(compare_gate.get("row_contract"), dict) else {}
    handoff = {
        "handoff_status": "ready_for_explicit_dual_execution_authorization",
        "why_this_bundle_exists": [
            "future_stage9950_100m_and_stage9953_gemma_must_stay_on_the_same_manifest",
            "the blended_web_recovery_edit_localization_slice_is currently_the_narrowest_live_path_to_a_truthful_same-surface_comparison",
            "comparison_is_not_permitted_until_stage9954_contract_conditions_are_met",
        ],
        "hundred_m_execution": {
            "future_stage": candidate_100m.get("future_stage"),
            "future_run_id": candidate_100m.get("future_run_id"),
            "future_output_dir": candidate_100m.get("future_output_dir"),
            "command": hundred_m_command,
        },
        "gemma_execution": {
            "future_stage": 9953,
            "cell_key": gemma_entry.get("cell_key"),
            "future_output_stub": ((gemma_entry.get("review_packet_paths") or {}).get("same_prompt_surface_gemma12b_outputs")),
            "command": gemma_command,
        },
        "same_manifest_comparison_gate": {
            "gate_path": display(COMPARE_GATE),
            "claim_permitted_only_after": list((compare_gate.get("gate_rows") or {}).get("same_manifest_claim_permitted_only_after") or []),
        },
        "row_contract": {
            "hundred_m_rows": row_contract.get("hundred_m_rows"),
            "gemma_rows": row_contract.get("gemma_rows"),
            "hundred_m_web_rows": row_contract.get("hundred_m_web_rows"),
            "gemma_web_rows": row_contract.get("gemma_web_rows"),
            "hundred_m_split_counts": dict(row_contract.get("hundred_m_split_counts") or {}),
            "gemma_split_counts": dict(row_contract.get("gemma_split_counts") or {}),
            "targeted_web_refresh_preserved_100m": row_contract.get("targeted_web_refresh_preserved_100m"),
            "targeted_web_refresh_preserved_gemma": row_contract.get("targeted_web_refresh_preserved_gemma"),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }

    metrics = {
        "hundred_m_future_stage": handoff["hundred_m_execution"]["future_stage"],
        "gemma_future_stage": handoff["gemma_execution"]["future_stage"],
        "row_contract_ok": row_contract.get("hundred_m_rows") == 72 and row_contract.get("gemma_rows") == 72 and row_contract.get("hundred_m_web_rows") == 27 and row_contract.get("gemma_web_rows") == 27,
        "dual_execution_ready_when_authorized": handoff["handoff_status"] == "ready_for_explicit_dual_execution_authorization",
        "claim_after_conditions": len(handoff["same_manifest_comparison_gate"]["claim_permitted_only_after"]),
    }
    if metrics["hundred_m_future_stage"] != 9950:
        failures.append("hundred_m_future_stage_not_9950")
    if metrics["gemma_future_stage"] != 9953:
        failures.append("gemma_future_stage_not_9953")
    if metrics["row_contract_ok"] is not True:
        failures.append("row_contract_not_ok")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "handoff_bundle": handoff,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_bundle()
    BUNDLE.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use this bundle when execution is explicitly authorized: run the stage9950 100M command, run the matching Gemma queue command, then compare only those outputs under the stage9954 same-manifest gate."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"bundle": display(BUNDLE), "doc": display(DOC)},
        "decision": "Materialized a single execution handoff bundle that joins the first blended 100M run, the matching Gemma run, and the same-manifest comparison gate into one narrow comparison packet.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9955 Blended Same-Manifest Execution Handoff Bundle",
        "",
        f"Passed: `{summary['passed']}`",
        f"100M future stage: `{built['metrics']['hundred_m_future_stage']}`",
        f"Gemma future stage: `{built['metrics']['gemma_future_stage']}`",
        f"Row contract ok: `{built['metrics']['row_contract_ok']}`",
        "",
        summary["decision"],
        "",
        "This stage does not authorize execution. It only joins the two future runs and the comparison gate into one bundle.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
