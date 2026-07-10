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
STAGE = 9954
NAME = "stage9954_blended_edit_localization_same_manifest_comparison_gate"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GATE = OUT_DIR / "blended_edit_localization_same_manifest_comparison_gate.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_EDIT_LOCALIZATION_SAME_MANIFEST_COMPARISON_GATE_STAGE9954.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
ACCEPT_100M = ROOT / "runs/local/artifacts/stage9951_blended_edit_localization_output_acceptance_audit/blended_edit_localization_output_acceptance_audit.json"
GEMMA_QUEUE = ROOT / "runs/local/artifacts/stage9952_blended_edit_localization_gemma_request/blended_edit_localization_gemma_queue.json"
GEMMA_PACKETS = ROOT / "runs/local/artifacts/stage9952_blended_edit_localization_gemma_request/blended_edit_localization_gemma_packets.jsonl"
RUNNER_SURFACE = ROOT / "runs/local/artifacts/stage9768_local_ollama_gemma_runner_surface/local_ollama_gemma_runner_surface.json"


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


def build_gate() -> dict[str, Any]:
    accept_100m = load_json(ACCEPT_100M)
    gemma_queue = load_json(GEMMA_QUEUE)
    gemma_packets = load_jsonl(GEMMA_PACKETS)
    runner_surface = load_json(RUNNER_SURFACE)
    failures: list[str] = []

    future_run = accept_100m.get("future_run") if isinstance(accept_100m.get("future_run"), dict) else {}
    blend_100m = accept_100m.get("blend_invariants") if isinstance(accept_100m.get("blend_invariants"), dict) else {}
    queue_entries = [row for row in (gemma_queue.get("queue_entries") or []) if isinstance(row, dict)]
    queue_row = queue_entries[0] if queue_entries else {}
    packet = gemma_packets[0] if gemma_packets else {}
    gemma_same_surface = packet.get("same_surface_packet") if isinstance(packet.get("same_surface_packet"), dict) else {}
    gemma_blend = packet.get("blend_invariants") if isinstance(packet.get("blend_invariants"), dict) else {}

    if future_run.get("selected_surface") != "edit_localization":
        failures.append("stage9951_not_edit_localization")
    if queue_row.get("skill_area") != "edit_localization":
        failures.append("stage9952_queue_not_edit_localization")
    if runner_surface.get("passed") is not True:
        failures.append("stage9768_runner_surface_not_passed")

    row_contract = {
        "hundred_m_rows": blend_100m.get("expected_rows"),
        "gemma_rows": gemma_same_surface.get("row_count"),
        "hundred_m_web_rows": blend_100m.get("expected_web_rows"),
        "gemma_web_rows": gemma_same_surface.get("expected_web_rows"),
        "hundred_m_split_counts": dict(blend_100m.get("expected_split_counts") or {}),
        "gemma_split_counts": dict(gemma_same_surface.get("split_counts") or {}),
        "same_manifest_path_100m": future_run.get("future_output_dir"),
        "same_manifest_path_gemma_source": gemma_same_surface.get("source_manifest"),
        "targeted_web_refresh_preserved_100m": blend_100m.get("candidate_targeted_web_refresh_preserved"),
        "targeted_web_refresh_preserved_gemma": gemma_blend.get("targeted_web_refresh_preserved"),
    }
    if row_contract["hundred_m_rows"] != 72 or row_contract["gemma_rows"] != 72:
        failures.append("row_count_contract_not_72")
    if row_contract["hundred_m_web_rows"] != 27 or row_contract["gemma_web_rows"] != 27:
        failures.append("web_row_contract_not_27")
    if row_contract["targeted_web_refresh_preserved_100m"] is not True:
        failures.append("hundred_m_targeted_web_refresh_not_preserved")
    if row_contract["targeted_web_refresh_preserved_gemma"] is not True:
        failures.append("gemma_targeted_web_refresh_not_preserved")

    gate_rows = {
        "future_stage_100m": future_run.get("future_stage"),
        "future_run_id_100m": future_run.get("future_run_id"),
        "future_output_dir_100m": future_run.get("future_output_dir"),
        "future_gemma_output_stub": ((queue_row.get("review_packet_paths") or {}).get("same_prompt_surface_gemma12b_outputs")),
        "future_gemma_ready_when_authorized": queue_row.get("ready_for_gemma_when_authorized"),
        "same_manifest_claim_permitted_only_after": [
            "stage9950_output_acceptance_ready",
            "stage9953_gemma_outputs_exist",
            "same_manifest_row_contract_still_matches_72_total_27_web",
            "no_mixed_surface_or_mixed_manifest_comparison",
        ],
    }
    if gate_rows["future_stage_100m"] != 9950:
        failures.append("future_stage_100m_not_9950")
    if gate_rows["future_gemma_ready_when_authorized"] is not True:
        failures.append("future_gemma_not_ready_when_authorized")

    metrics = {
        "same_manifest_row_contract_ok": not any(
            failure in failures
            for failure in [
                "row_count_contract_not_72",
                "web_row_contract_not_27",
                "hundred_m_targeted_web_refresh_not_preserved",
                "gemma_targeted_web_refresh_not_preserved",
            ]
        ),
        "runner_surface_ready": runner_surface.get("passed") is True,
        "future_stage_100m": gate_rows["future_stage_100m"],
        "future_gemma_queue_entries": len(queue_entries),
        "hundred_m_expected_rows": row_contract["hundred_m_rows"],
        "gemma_expected_rows": row_contract["gemma_rows"],
        "hundred_m_expected_web_rows": row_contract["hundred_m_web_rows"],
        "gemma_expected_web_rows": row_contract["gemma_web_rows"],
        "comparison_ready_now": False,
    }

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "row_contract": row_contract,
        "gate_rows": gate_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_gate()
    GATE.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "After Stage9950 and the matching Gemma execution both exist, compare only those same-manifest outputs and keep the claim scoped to this blended edit-localization surface unless broader multilingual evidence is regenerated on the same package."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"gate": display(GATE), "doc": display(DOC)},
        "decision": "Materialized the same-manifest comparison gate for the first blended edit-localization slice so future 100M and Gemma outputs are compared only if they preserve the shared 72-row / 27-web-row contract and remain on the exact same manifest.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9954 Blended Edit Localization Same-Manifest Comparison Gate",
        "",
        f"Passed: `{summary['passed']}`",
        f"100M expected rows: `{built['metrics']['hundred_m_expected_rows']}`",
        f"Gemma expected rows: `{built['metrics']['gemma_expected_rows']}`",
        f"100M expected web rows: `{built['metrics']['hundred_m_expected_web_rows']}`",
        f"Gemma expected web rows: `{built['metrics']['gemma_expected_web_rows']}`",
        "",
        summary["decision"],
        "",
        "This stage does not compare outputs yet. It only freezes the contract that future comparison must obey.",
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
