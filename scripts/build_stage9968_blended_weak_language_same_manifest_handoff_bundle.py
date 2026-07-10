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
STAGE = 9968
NAME = "stage9968_blended_weak_language_same_manifest_handoff_bundle"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BUNDLE = OUT_DIR / "blended_weak_language_same_manifest_handoff_bundle.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_WEAK_LANGUAGE_SAME_MANIFEST_HANDOFF_BUNDLE_STAGE9968.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
CANDIDATE_100M = ROOT / "runs/local/artifacts/stage9967_blended_weak_language_execution_readiness_gate/first_surface_execution_candidate_edit_localization.json"
REQUEST_100M = ROOT / "runs/local/artifacts/stage9966_blended_weak_language_target100m_execution_request/surface_requests/edit_localization.json"
OLLAMA_SURFACE = ROOT / "runs/local/artifacts/stage9768_local_ollama_gemma_runner_surface/local_ollama_gemma_runner_surface.json"
RUNNER = ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py"

CELL_KEY = "blended_target100m::edit_localization::same_manifest_weak_language_gemma12b"
FUTURE_GEMMA_STAGE = 9971
FUTURE_GEMMA_STAGE_PREFIX = "stage9971_"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


load_jsonl = _load_symbol("stage9968_runner_load_jsonl", RUNNER, "load_jsonl")
prompt_surface_hash = _load_symbol("stage9968_runner_prompt_surface_hash", RUNNER, "prompt_surface_hash")


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
    return f"runs/local/artifacts/{FUTURE_GEMMA_STAGE_PREFIX}blended_weak_language_gemma_execution/same_prompt_surface_gemma12b_outputs.json"


def selected_manifest_rows(manifest_path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(manifest_path)
    selected = [row for row in rows if str(row.get("split") or "") in {"eval", "strict_eval"}]
    selected.sort(key=lambda row: str(row.get("row_id") or ""))
    return selected


def build_bundle() -> dict[str, Any]:
    candidate_100m = load_json(CANDIDATE_100M)
    request_100m = load_json(REQUEST_100M)
    ollama = load_json(OLLAMA_SURFACE)
    failures: list[str] = []

    manifest_path = ROOT / str(request_100m.get("manifest") or "")
    same_manifest_rows = selected_manifest_rows(manifest_path) if manifest_path.exists() else []
    same_manifest_row_ids = [str(row.get("row_id") or "") for row in same_manifest_rows]
    same_manifest_surface_hash = prompt_surface_hash(same_manifest_rows) if same_manifest_rows else None

    if candidate_100m.get("selected_surface") != "edit_localization":
        failures.append("stage9967_candidate_not_edit_localization")
    if request_100m.get("surface") != "edit_localization":
        failures.append("stage9966_request_not_edit_localization")
    if ollama.get("passed") is not True:
        failures.append("stage9768_ollama_surface_not_passed")
    if not same_manifest_rows:
        failures.append("same_manifest_eval_and_strict_rows_missing")

    hundred_m_command = [str(item) for item in (candidate_100m.get("command") or [])]
    gemma_command = [
        "python",
        str(RUNNER.relative_to(ROOT)),
        "--queue",
        "runs/local/artifacts/stage9968_blended_weak_language_same_manifest_handoff_bundle/blended_weak_language_gemma_queue.json",
        "--packets",
        "runs/local/artifacts/stage9968_blended_weak_language_same_manifest_handoff_bundle/blended_weak_language_gemma_packets.jsonl",
        "--model",
        "gemma3:12b",
        "--cell-key",
        CELL_KEY,
    ]

    row_contract = {
        "hundred_m_rows": int(request_100m.get("rows") or 0),
        "gemma_rows": int(request_100m.get("rows") or 0),
        "hundred_m_python_rows": int((request_100m.get("language_counts") or {}).get("python", 0)),
        "gemma_python_rows": int((request_100m.get("language_counts") or {}).get("python", 0)),
        "hundred_m_c_cpp_rows": int((request_100m.get("language_counts") or {}).get("c_cpp", 0)),
        "gemma_c_cpp_rows": int((request_100m.get("language_counts") or {}).get("c_cpp", 0)),
        "hundred_m_web_rows": int((request_100m.get("language_counts") or {}).get("web_js_ts_html", 0)),
        "gemma_web_rows": int((request_100m.get("language_counts") or {}).get("web_js_ts_html", 0)),
        "hundred_m_split_counts": dict(request_100m.get("split_counts") or {}),
        "gemma_split_counts": dict(request_100m.get("split_counts") or {}),
        "same_manifest_compare_rows": len(same_manifest_row_ids),
        "surface_hash": same_manifest_surface_hash,
    }

    packet = {
        "cell_key": CELL_KEY,
        "language_family": "multilingual",
        "skill_area": "edit_localization",
        "same_surface_packet": {
            "source_manifest": request_100m.get("manifest"),
            "surface_hash": same_manifest_surface_hash,
            "row_ids": same_manifest_row_ids,
            "split_counts": dict(request_100m.get("split_counts") or {}),
            "row_count": request_100m.get("rows"),
            "expected_python_rows": (request_100m.get("language_counts") or {}).get("python"),
            "expected_c_cpp_rows": (request_100m.get("language_counts") or {}).get("c_cpp"),
            "expected_web_rows": (request_100m.get("language_counts") or {}).get("web_js_ts_html"),
        },
        "review_packet_paths": {
            "same_prompt_surface_gemma12b_outputs": _future_output_stub(),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }

    queue_entry = {
        "cell_key": CELL_KEY,
        "language_family": "multilingual",
        "skill_area": "edit_localization",
        "priority_rank": 1,
        "priority_reason": "same-manifest Gemma-12B comparison for the successor weak-language recovery execution candidate",
        "ready_for_gemma_when_authorized": ollama.get("passed") is True,
        "gemma_execution_authorized_now": False,
        "harness_execution_authorized_now": False,
        "required_missing_evidence": [],
        "remaining_blockers": [
            "explicit_gemma_execution_authorization",
            "stage9965_100m_outputs_should_exist_before_final_same_surface_claim",
        ],
        "same_surface_packet": dict(packet["same_surface_packet"]),
        "review_packet_paths": dict(packet["review_packet_paths"]),
    }

    handoff = {
        "handoff_status": "ready_for_explicit_dual_execution_authorization",
        "why_this_bundle_exists": [
            "future_stage9965_100m_and_stage9971_gemma_must_stay_on_the_same_manifest",
            "the successor weak-language recovery slice is the current best path to close python and c_cpp while preserving web recovery",
            "comparison_is_not_permitted_until both real outputs exist on this exact manifest",
        ],
        "hundred_m_execution": {
            "future_stage": candidate_100m.get("future_stage"),
            "future_run_id": candidate_100m.get("future_run_id"),
            "future_output_dir": candidate_100m.get("future_output_dir"),
            "command": hundred_m_command,
        },
        "gemma_execution": {
            "future_stage": FUTURE_GEMMA_STAGE,
            "cell_key": CELL_KEY,
            "future_output_stub": _future_output_stub(),
            "command": gemma_command,
        },
        "gemma_queue_entries": [queue_entry],
        "gemma_packets": [packet],
        "comparison_rule": {
            "same_manifest_only": True,
            "claim_permitted_only_after": [
                "stage9965_output_acceptance_ready",
                "stage9971_gemma_outputs_exist",
                "same_manifest_row_contract_still_matches_120_total_24_python_30_c_cpp_45_web",
                "no_mixed_surface_or_mixed_manifest_comparison",
            ],
        },
        "row_contract": row_contract,
        "authority": dict(AUTHORITY_CLOSED),
    }

    metrics = {
        "hundred_m_future_stage": handoff["hundred_m_execution"]["future_stage"],
        "gemma_future_stage": handoff["gemma_execution"]["future_stage"],
        "row_contract_ok": row_contract["hundred_m_rows"] == 120 and row_contract["gemma_rows"] == 120 and row_contract["hundred_m_python_rows"] == 24 and row_contract["hundred_m_c_cpp_rows"] == 30 and row_contract["hundred_m_web_rows"] == 45,
        "dual_execution_ready_when_authorized": handoff["handoff_status"] == "ready_for_explicit_dual_execution_authorization",
        "same_manifest_compare_rows": row_contract["same_manifest_compare_rows"],
        "local_gemma3_12b_present": bool((ollama.get("ollama_runtime") or {}).get("local_gemma_model_id") == "gemma3:12b"),
    }
    if metrics["hundred_m_future_stage"] != 9965:
        failures.append("hundred_m_future_stage_not_9965")
    if metrics["gemma_future_stage"] != FUTURE_GEMMA_STAGE:
        failures.append("gemma_future_stage_not_9971")
    if metrics["row_contract_ok"] is not True:
        failures.append("row_contract_not_ok")
    if metrics["same_manifest_compare_rows"] != 80:
        failures.append("same_manifest_compare_rows_not_80")
    if metrics["local_gemma3_12b_present"] is not True:
        failures.append("local_gemma3_12b_not_present")

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
    queue_path = OUT_DIR / "blended_weak_language_gemma_queue.json"
    packets_path = OUT_DIR / "blended_weak_language_gemma_packets.jsonl"
    queue_path.write_text(json.dumps({"queue_entries": built["handoff_bundle"]["gemma_queue_entries"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    packets_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in built["handoff_bundle"]["gemma_packets"]), encoding="utf-8")
    next_step = "Use this bundle when execution is explicitly authorized: run the stage9965 100M command, run the matching Gemma queue command, then compare only those outputs on the exact same 120-row manifest."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "bundle": display(BUNDLE),
            "gemma_queue": display(queue_path),
            "gemma_packets": display(packets_path),
            "doc": display(DOC),
        },
        "decision": "Materialized a single same-manifest handoff bundle that joins the successor weak-language 100M run, the matching Gemma run, and the comparison rule into one comparison packet.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9968 Blended Weak-Language Same-Manifest Handoff Bundle",
        "",
        f"Passed: `{summary['passed']}`",
        f"100M future stage: `{built['metrics']['hundred_m_future_stage']}`",
        f"Gemma future stage: `{built['metrics']['gemma_future_stage']}`",
        f"Same-manifest compare rows: `{built['metrics']['same_manifest_compare_rows']}`",
        "",
        summary["decision"],
        "",
        "This stage does not authorize execution. It only joins the two future runs and the comparison rule into one bundle.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
