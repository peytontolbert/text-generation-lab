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
STAGE = 9757
NAME = "stage9757_full_product_harness_review_stub_files"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "full_product_harness_review_stub_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_PRODUCT_HARNESS_REVIEW_STUB_FILES_STAGE9757.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_PACKETS = ROOT / "runs/local/artifacts/stage9756_full_product_harness_review_packets/full_product_harness_review_packets.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _abs(rel_path: str) -> Path:
    return ROOT / rel_path


def materialize_stub_files(packets: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    manifest_rows: list[dict[str, Any]] = []
    for packet in packets:
        cell_key = str(packet.get("cell_key") or "")
        paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        required_keys = [
            "harness_run_id",
            "same_task_pack_as_gemma12b",
            "tool_trace_spans",
            "verifier_results",
            "patch_minimality_or_abstain_scores",
            "expert_maintainer_rubric_scores",
            "anti_cheat_cards",
            "packet_dir",
        ]
        if any(not str(paths.get(key) or "") for key in required_keys):
            failures.append(f"missing_stub_paths:{cell_key}")
            continue
        harness_run_path = _abs(str(paths["harness_run_id"]))
        same_pack_path = _abs(str(paths["same_task_pack_as_gemma12b"]))
        trace_path = _abs(str(paths["tool_trace_spans"]))
        verifier_path = _abs(str(paths["verifier_results"]))
        patch_path = _abs(str(paths["patch_minimality_or_abstain_scores"]))
        rubric_path = _abs(str(paths["expert_maintainer_rubric_scores"]))
        anti_path = _abs(str(paths["anti_cheat_cards"]))
        packet_dir = _abs(str(paths["packet_dir"]))

        rubric_template = packet.get("expert_maintainer_review_template") if isinstance(packet.get("expert_maintainer_review_template"), dict) else {}
        anti_template = packet.get("anti_cheat_review_template") if isinstance(packet.get("anti_cheat_review_template"), dict) else {}

        _write_text(harness_run_path, "\n".join([
            f"cell_key={cell_key}",
            "status=pending_harness_run_id",
            "harness_run_id=",
            "notes=fill only with real harness run id from the full-product execution surface",
            "",
        ]))
        _write_json(same_pack_path, {
            "cell_key": cell_key,
            "status": "pending_same_task_pack_gemma_comparison",
            "same_task_pack_verified": False,
            "hundred_m_artifact_paths": [],
            "gemma12b_artifact_paths": [],
            "same_task_pack_hash": None,
            "authority": dict(AUTHORITY_CLOSED),
        })
        _write_jsonl(trace_path, [])
        _write_json(verifier_path, {
            "cell_key": cell_key,
            "status": "pending_verifier_results",
            "passed": False,
            "verifier_runs": [],
            "authority": dict(AUTHORITY_CLOSED),
        })
        _write_json(patch_path, {
            "cell_key": cell_key,
            "status": "pending_patch_minimality_or_abstain_scores",
            "passed": False,
            "scores": [],
            "authority": dict(AUTHORITY_CLOSED),
        })
        _write_json(rubric_path, {
            "cell_key": cell_key,
            "status": "pending_human_review",
            "rubric_version": rubric_template.get("rubric_version"),
            "must_pass_all_subskills": rubric_template.get("must_pass_all_subskills") is True,
            "passed": False,
            "subskills": {name: None for name in rubric_template.get("subskills_required") or []},
            "failure_trace_refs": [],
            "reviewer_notes": [],
            "authority": dict(AUTHORITY_CLOSED),
        })
        _write_json(anti_path, {
            "cell_key": cell_key,
            "status": "pending_cell_specific_review",
            "passed": False,
            "challenge_requirements": anti_template.get("challenge_requirements") or [],
            "must_attach_cell_specific_cards": anti_template.get("must_attach_cell_specific_cards") is True,
            "reviewer_notes": [],
            "authority": dict(AUTHORITY_CLOSED),
        })
        manifest_rows.append({
            "cell_key": cell_key,
            "packet_dir": str(packet_dir.relative_to(ROOT)),
            "harness_run_id": str(harness_run_path.relative_to(ROOT)),
            "same_task_pack_as_gemma12b": str(same_pack_path.relative_to(ROOT)),
            "tool_trace_spans": str(trace_path.relative_to(ROOT)),
            "verifier_results": str(verifier_path.relative_to(ROOT)),
            "patch_minimality_or_abstain_scores": str(patch_path.relative_to(ROOT)),
            "expert_maintainer_rubric_scores": str(rubric_path.relative_to(ROOT)),
            "anti_cheat_cards": str(anti_path.relative_to(ROOT)),
        })

    metrics = {
        "packets": len(packets),
        "stub_manifests": len(manifest_rows),
        "harness_run_id_stub_files": len(manifest_rows),
        "same_task_pack_stub_files": len(manifest_rows),
        "tool_trace_stub_files": len(manifest_rows),
        "verifier_result_stub_files": len(manifest_rows),
        "patch_score_stub_files": len(manifest_rows),
        "rubric_stub_files": len(manifest_rows),
        "anti_cheat_stub_files": len(manifest_rows),
    }
    if metrics["packets"] != 36:
        failures.append("packets_not_36")
    if metrics["stub_manifests"] != 36:
        failures.append("stub_manifest_rows_not_36")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "manifest_rows": manifest_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = materialize_stub_files(load_jsonl(SOURCE_PACKETS))
    MANIFEST.write_text(json.dumps({
        "stage": STAGE,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "rows": built["manifest_rows"],
        "authority": dict(AUTHORITY_CLOSED),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Fill the Stage9757 rubric and anti-cheat stub files plus any pre-execution harness metadata that can be attached now, "
        "then populate the execution stubs only after a concrete full-product harness runner surface is recovered or authorized."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **built["metrics"],
        },
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized the physical harness-side stub files referenced by the 36 full-product review packets so review-prep and future execution have stable on-disk targets.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9757 Full Product Harness Review Stub Files",
        "",
        f"Passed: `{summary['passed']}`",
        f"Packets: `{summary['metrics']['packets']}`",
        f"Harness run-id stubs: `{summary['metrics']['harness_run_id_stub_files']}`",
        f"Same-task-pack stubs: `{summary['metrics']['same_task_pack_stub_files']}`",
        f"Tool-trace stubs: `{summary['metrics']['tool_trace_stub_files']}`",
        f"Verifier-result stubs: `{summary['metrics']['verifier_result_stub_files']}`",
        f"Patch-score stubs: `{summary['metrics']['patch_score_stub_files']}`",
        "",
        "This stage writes the actual placeholder files referenced by Stage9756 so harness review preparation and future full-product execution can attach evidence directly to stable on-disk paths.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "packets": summary["metrics"]["packets"],
        "harness_run_id_stub_files": summary["metrics"]["harness_run_id_stub_files"],
        "same_task_pack_stub_files": summary["metrics"]["same_task_pack_stub_files"],
        "tool_trace_stub_files": summary["metrics"]["tool_trace_stub_files"],
        "verifier_result_stub_files": summary["metrics"]["verifier_result_stub_files"],
        "patch_score_stub_files": summary["metrics"]["patch_score_stub_files"],
        "rubric_stub_files": summary["metrics"]["rubric_stub_files"],
        "anti_cheat_stub_files": summary["metrics"]["anti_cheat_stub_files"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
