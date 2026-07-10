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
STAGE = 9753
NAME = "stage9753_supported_standalone_review_stub_files"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "supported_standalone_review_stub_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORTED_STANDALONE_REVIEW_STUB_FILES_STAGE9753.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"


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
        rubric_path = _abs(str(paths.get("expert_maintainer_rubric_scores") or ""))
        anti_cheat_path = _abs(str(paths.get("anti_cheat_cards") or ""))
        gemma_path = _abs(str(paths.get("same_prompt_surface_gemma12b_outputs") or ""))
        checkpoint_path = _abs(str(paths.get("frozen_export_or_checkpoint_hash") or ""))
        packet_dir = _abs(str(paths.get("packet_dir") or ""))
        if not all([str(paths.get("expert_maintainer_rubric_scores") or ""), str(paths.get("anti_cheat_cards") or ""), str(paths.get("same_prompt_surface_gemma12b_outputs") or ""), str(paths.get("frozen_export_or_checkpoint_hash") or "")]):
            failures.append(f"missing_stub_paths:{cell_key}")
            continue

        rubric_template = packet.get("expert_maintainer_review_template") if isinstance(packet.get("expert_maintainer_review_template"), dict) else {}
        anti_template = packet.get("anti_cheat_review_template") if isinstance(packet.get("anti_cheat_review_template"), dict) else {}
        same_surface_packet = packet.get("same_surface_packet") if isinstance(packet.get("same_surface_packet"), dict) else {}
        global_gate = packet.get("global_anti_hack_gate") if isinstance(packet.get("global_anti_hack_gate"), dict) else {}

        _write_json(rubric_path, {
            "cell_key": cell_key,
            "status": "pending_human_review",
            "rubric_version": rubric_template.get("rubric_version"),
            "must_pass_all_subskills": rubric_template.get("must_pass_all_subskills") is True,
            "passed": False,
            "subskills": {name: None for name in rubric_template.get("subskills_required") or []},
            "failure_trace_refs": [],
            "reviewer_notes": [],
            "source_100m_score": same_surface_packet.get("eval_exact"),
            "authority": dict(AUTHORITY_CLOSED),
        })
        _write_json(anti_cheat_path, {
            "cell_key": cell_key,
            "status": "pending_cell_specific_review",
            "passed": False,
            "must_pass_global_stage9717_gate": anti_template.get("must_pass_global_stage9717_gate") is True,
            "global_stage9717_gate_passed": global_gate.get("passed") is True,
            "challenge_families": [
                {
                    "challenge_family": name,
                    "cell_specific_card_present": False,
                    "passed": False,
                    "notes": [],
                }
                for name in anti_template.get("challenge_families") or []
            ],
            "reviewer_notes": [],
            "authority": dict(AUTHORITY_CLOSED),
        })
        _write_json(gemma_path, {
            "cell_key": cell_key,
            "status": "pending_gemma_execution",
            "authorized_now": False,
            "same_surface_verified": False,
            "prompt_surface_hash_gemma12b": None,
            "score_gemma12b": None,
            "output_artifact_paths": [],
            "notes": [
                "populate_only_after_real_gemma_execution_on_matching_prompt_surface",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        })
        _write_text(checkpoint_path, "\n".join([
            f"cell_key={cell_key}",
            "status=pending_checkpoint_or_export_hash",
            "frozen_export_or_checkpoint_hash=",
            "notes=fill only with real frozen export or checkpoint hash tied to the 100m side used for comparison",
            "",
        ]))

        manifest_rows.append({
            "cell_key": cell_key,
            "packet_dir": str(packet_dir.relative_to(ROOT)),
            "expert_maintainer_rubric_scores": str(rubric_path.relative_to(ROOT)),
            "anti_cheat_cards": str(anti_cheat_path.relative_to(ROOT)),
            "same_prompt_surface_gemma12b_outputs": str(gemma_path.relative_to(ROOT)),
            "frozen_export_or_checkpoint_hash": str(checkpoint_path.relative_to(ROOT)),
        })

    metrics = {
        "packets": len(packets),
        "stub_manifests": len(manifest_rows),
        "rubric_stub_files": len(manifest_rows),
        "anti_cheat_stub_files": len(manifest_rows),
        "gemma_stub_files": len(manifest_rows),
        "checkpoint_stub_files": len(manifest_rows),
    }
    if metrics["packets"] != 13:
        failures.append("packets_not_13")
    if metrics["stub_manifests"] != 13:
        failures.append("stub_manifest_rows_not_13")

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
    packets = load_jsonl(SOURCE_PACKETS)
    built = materialize_stub_files(packets)
    MANIFEST.write_text(json.dumps({
        "stage": STAGE,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "rows": built["manifest_rows"],
        "authority": dict(AUTHORITY_CLOSED),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Fill the Stage9753 rubric and anti-cheat stub files with real reviewer judgments and attach the real 100M checkpoint hash, "
        "then populate the adjacent Gemma stub files after same-surface Gemma execution becomes available."
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
        "decision": "Materialized the physical rubric, anti-cheat, Gemma-output, and checkpoint stub files referenced by the 13 supported standalone review packets.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9753 Supported Standalone Review Stub Files",
        "",
        f"Passed: `{summary['passed']}`",
        f"Packets: `{summary['metrics']['packets']}`",
        f"Rubric stubs: `{summary['metrics']['rubric_stub_files']}`",
        f"Anti-cheat stubs: `{summary['metrics']['anti_cheat_stub_files']}`",
        f"Gemma stubs: `{summary['metrics']['gemma_stub_files']}`",
        f"Checkpoint stubs: `{summary['metrics']['checkpoint_stub_files']}`",
        "",
        "This stage writes the actual placeholder files referenced by Stage9752 so human review and future Gemma execution can attach evidence directly to stable on-disk paths instead of only to planned slots.",
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
        "rubric_stub_files": summary["metrics"]["rubric_stub_files"],
        "anti_cheat_stub_files": summary["metrics"]["anti_cheat_stub_files"],
        "gemma_stub_files": summary["metrics"]["gemma_stub_files"],
        "checkpoint_stub_files": summary["metrics"]["checkpoint_stub_files"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
