#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9952
NAME = "stage9952_blended_edit_localization_gemma_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE = OUT_DIR / "blended_edit_localization_gemma_queue.json"
PACKETS = OUT_DIR / "blended_edit_localization_gemma_packets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_EDIT_LOCALIZATION_GEMMA_REQUEST_STAGE9952.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUEST = ROOT / "runs/local/artifacts/stage9948_web_targeted_blended_target100m_execution_request/surface_requests/edit_localization.json"
CANDIDATE = ROOT / "runs/local/artifacts/stage9949_web_targeted_blended_execution_readiness_gate/first_surface_execution_candidate_edit_localization.json"
ACCEPTANCE = ROOT / "runs/local/artifacts/stage9951_blended_edit_localization_output_acceptance_audit/blended_edit_localization_output_acceptance_audit.json"
OLLAMA_SURFACE = ROOT / "runs/local/artifacts/stage9768_local_ollama_gemma_runner_surface/local_ollama_gemma_runner_surface.json"
RUNNER = ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py"

CELL_KEY = "blended_target100m::edit_localization::same_manifest_gemma12b"
FUTURE_STAGE = 9953
FUTURE_STAGE_PREFIX = "stage9953_"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


load_jsonl = _load_symbol("stage9952_runner_load_jsonl", RUNNER, "load_jsonl")
prompt_surface_hash = _load_symbol("stage9952_runner_prompt_surface_hash", RUNNER, "prompt_surface_hash")


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


def _future_output_stub() -> str:
    return f"runs/local/artifacts/{FUTURE_STAGE_PREFIX}blended_edit_localization_gemma_execution/same_prompt_surface_gemma12b_outputs.json"


def selected_manifest_rows(manifest_path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(manifest_path)
    selected = [row for row in rows if str(row.get("split") or "") in {"eval", "strict_eval"}]
    selected.sort(key=lambda row: str(row.get("row_id") or ""))
    return selected


def build_queue() -> dict[str, Any]:
    request = load_json(REQUEST)
    candidate = load_json(CANDIDATE)
    acceptance = load_json(ACCEPTANCE)
    ollama = load_json(OLLAMA_SURFACE)
    failures: list[str] = []
    manifest_path = ROOT / str(request.get("manifest") or "")
    same_manifest_rows = selected_manifest_rows(manifest_path) if manifest_path.exists() else []
    same_manifest_row_ids = [str(row.get("row_id") or "") for row in same_manifest_rows]
    same_manifest_surface_hash = prompt_surface_hash(same_manifest_rows) if same_manifest_rows else None

    if request.get("surface") != "edit_localization":
        failures.append("stage9948_request_not_edit_localization")
    if candidate.get("selected_surface") != "edit_localization":
        failures.append("stage9949_candidate_not_edit_localization")
    if acceptance.get("future_run", {}).get("selected_surface") != "edit_localization":
        failures.append("stage9951_acceptance_not_edit_localization")
    if ollama.get("passed") is not True:
        failures.append("stage9768_ollama_surface_not_passed")
    if not same_manifest_rows:
        failures.append("same_manifest_eval_and_strict_rows_missing")

    packet = {
        "cell_key": CELL_KEY,
        "language_family": "multilingual",
        "skill_area": "edit_localization",
        "same_surface_packet": {
            "source_manifest": request.get("manifest"),
            "surface_hash": same_manifest_surface_hash,
            "row_ids": same_manifest_row_ids,
            "split_counts": dict(request.get("split_counts") or {}),
            "row_count": request.get("rows"),
            "expected_web_rows": (request.get("language_counts") or {}).get("web_js_ts_html"),
        },
        "review_packet_paths": {
            "same_prompt_surface_gemma12b_outputs": _future_output_stub(),
        },
        "blend_invariants": {
            "rows": request.get("rows"),
            "web_rows": (request.get("language_counts") or {}).get("web_js_ts_html"),
            "split_counts": dict(request.get("split_counts") or {}),
            "targeted_web_refresh_preserved": ((candidate.get("blend_invariants") or {}).get("targeted_web_refresh_preserved") is True),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }

    queue_entry = {
        "cell_key": CELL_KEY,
        "language_family": "multilingual",
        "skill_area": "edit_localization",
        "priority_rank": 1,
        "priority_reason": "same-manifest Gemma-12B comparison for the first blended edit-localization execution candidate",
        "ready_for_gemma_when_authorized": ollama.get("passed") is True,
        "gemma_execution_authorized_now": False,
        "harness_execution_authorized_now": False,
        "required_missing_evidence": [],
        "remaining_blockers": [
            "explicit_gemma_execution_authorization",
            "stage9950_100m_outputs_should_exist_before_final_same_surface_claim",
        ],
        "same_surface_packet": dict(packet["same_surface_packet"]),
        "review_packet_paths": dict(packet["review_packet_paths"]),
    }

    runner_command = [
        "python",
        str(RUNNER.relative_to(ROOT)),
        "--queue",
        str(QUEUE.relative_to(ROOT)),
        "--packets",
        str(PACKETS.relative_to(ROOT)),
        "--model",
        "gemma3:12b",
        "--cell-key",
        CELL_KEY,
    ]

    metrics = {
        "queue_entries": 1,
        "edit_localization_rows": packet["same_surface_packet"]["row_count"],
        "edit_localization_web_rows": packet["same_surface_packet"]["expected_web_rows"],
        "same_manifest_compare_rows": len(same_manifest_row_ids),
        "local_gemma3_12b_present": bool((ollama.get("ollama_runtime") or {}).get("local_gemma_model_id") == "gemma3:12b"),
        "runner_script_exists": RUNNER.exists(),
    }
    if metrics["edit_localization_rows"] != 72:
        failures.append("edit_localization_rows_not_72")
    if metrics["edit_localization_web_rows"] != 27:
        failures.append("edit_localization_web_rows_not_27")
    if metrics["same_manifest_compare_rows"] != 48:
        failures.append("same_manifest_compare_rows_not_48")
    if metrics["local_gemma3_12b_present"] is not True:
        failures.append("local_gemma3_12b_not_present")
    if metrics["runner_script_exists"] is not True:
        failures.append("runner_script_missing")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "queue_entries": [queue_entry],
        "packets": [packet],
        "runner_command": runner_command,
        "future_gemma_output_stub": _future_output_stub(),
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_queue()
    QUEUE.write_text(json.dumps({"queue_entries": built["queue_entries"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    PACKETS.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in built["packets"]), encoding="utf-8")
    next_step = "Use this one-cell queue with the local Ollama runner when Gemma execution is explicitly authorized, then compare the resulting same-prompt outputs against the Stage9950 blended 100M run on the exact same manifest."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "queue": display(QUEUE),
            "packets": display(PACKETS),
            "doc": display(DOC),
        },
        "decision": "Materialized a same-manifest Gemma request for the blended Stage9950 edit-localization slice, reusing the local Ollama runner contract and preserving the blended 72-row / 27-web-row surface invariants.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9952 Blended Edit Localization Gemma Request",
                "",
                f"Passed: `{summary['passed']}`",
                f"Queue entries: `{built['metrics']['queue_entries']}`",
                f"Edit-localization rows: `{built['metrics']['edit_localization_rows']}`",
                f"Web rows: `{built['metrics']['edit_localization_web_rows']}`",
                f"Local gemma3:12b present: `{built['metrics']['local_gemma3_12b_present']}`",
                "",
                summary["decision"],
                "",
                "This stage only materializes the Gemma request packet and runner command. It does not authorize or execute Gemma.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": built["metrics"],
                "failures": built["failures"],
                "next_best_step": next_step,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
