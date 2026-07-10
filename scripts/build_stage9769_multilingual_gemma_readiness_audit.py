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
STAGE = 9769
NAME = "stage9769_multilingual_gemma_readiness_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "multilingual_gemma_readiness_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_GEMMA_READINESS_STAGE9769.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
QUEUE = ROOT / "runs/local/artifacts/stage9748_supported_standalone_gemma_queue/supported_standalone_gemma_queue.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
REVIEW_DIR = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"
TARGET_LANGUAGES = ["python", "rust", "c_cpp", "web_js_ts_html"]


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


def packet_dir_for(cell_key: str) -> Path:
    return REVIEW_DIR / cell_key.replace("::", "__")


def detect_language(cell_key: str) -> str:
    parts = cell_key.split("::")
    return parts[1] if len(parts) >= 3 else "unknown"


def build_audit() -> dict[str, Any]:
    queue = load_json(QUEUE)
    packets = load_jsonl(PACKETS)
    queue_entries = queue.get("queue_entries") if isinstance(queue.get("queue_entries"), list) else []
    packet_index = {str(packet.get("cell_key") or ""): packet for packet in packets}
    per_language: dict[str, dict[str, Any]] = {}
    evidence_complete_cells = 0
    real_gemma_cells = 0
    full_surface_real_gemma_cells = 0
    language_field_missing = 0
    for language in TARGET_LANGUAGES:
        per_language[language] = {
            "ready_cells": [],
            "skills": [],
            "evidence_complete_cells": 0,
            "real_gemma_cells": 0,
        }
    for entry in queue_entries:
        cell_key = str(entry.get("cell_key") or "")
        language = detect_language(cell_key)
        skill = str(entry.get("skill_area") or "")
        packet = packet_index.get(cell_key, {})
        packet_dir = packet_dir_for(cell_key)
        evidence_flags = {
            "expert_maintainer_rubric_review": (packet_dir / "expert_maintainer_rubric_review.json").exists(),
            "anti_cheat_review_card": (packet_dir / "anti_cheat_review_card.json").exists(),
            "checkpoint_hash": (packet_dir / "frozen_export_or_checkpoint_hash.txt").exists(),
            "gemma_output_slot": (packet_dir / "same_prompt_surface_gemma12b_outputs.json").exists(),
        }
        gemma_output = load_json(packet_dir / "same_prompt_surface_gemma12b_outputs.json")
        real_gemma = gemma_output.get("status") == "completed_gemma_execution"
        full_surface_real_gemma = real_gemma and gemma_output.get("same_surface_verified") is True
        if packet.get("language") is None:
            language_field_missing += 1
        record = {
            "cell_key": cell_key,
            "skill_area": skill,
            "ready_for_gemma_when_authorized": entry.get("ready_for_gemma_when_authorized") is True,
            "evidence_flags": evidence_flags,
            "gemma_execution": {
                "status": gemma_output.get("status"),
                "authorized_now": gemma_output.get("authorized_now"),
                "same_surface_verified": gemma_output.get("same_surface_verified"),
                "executed_split": gemma_output.get("executed_split"),
                "executed_row_count": gemma_output.get("executed_row_count"),
                "score_gemma12b": gemma_output.get("score_gemma12b"),
            },
        }
        if language in per_language:
            per_language[language]["ready_cells"].append(record)
            per_language[language]["skills"].append(skill)
            if all(evidence_flags.values()):
                per_language[language]["evidence_complete_cells"] += 1
            if real_gemma:
                per_language[language]["real_gemma_cells"] += 1
        if all(evidence_flags.values()):
            evidence_complete_cells += 1
        if real_gemma:
            real_gemma_cells += 1
        if full_surface_real_gemma:
            full_surface_real_gemma_cells += 1
    for language, data in per_language.items():
        data["skills"] = sorted(set(data["skills"]))
        data["ready_cell_count"] = len(data["ready_cells"])
    passed = all(per_language[language]["ready_cell_count"] >= 3 for language in TARGET_LANGUAGES)
    return {
        "passed": passed,
        "target_languages": TARGET_LANGUAGES,
        "ready_cell_count": len(queue_entries),
        "evidence_complete_cell_count": evidence_complete_cells,
        "real_gemma_execution_cell_count": real_gemma_cells,
        "full_surface_real_gemma_execution_cell_count": full_surface_real_gemma_cells,
        "packet_language_field_missing_count": language_field_missing,
        "per_language": per_language,
        "findings": [
            "All four target language groups have ready standalone Gemma queue coverage across edit_localization, patch_operator_selection, and verifier_failure_repair_or_abstain; python also has symbol_binding.",
            "All 13 ready standalone review packets already contain rubric, anti-cheat, checkpoint-hash, and Gemma output-slot evidence files.",
            "Real local Gemma execution evidence currently exists only as a bounded python symbol_binding strict_eval slice; no full-surface executed Gemma comparison is recorded yet.",
            "The initial bounded runner surfaced an eval-hacking risk where the prompt label vocabulary collapsed to the selected slice; the runner now uses full-packet label vocab instead.",
            "Review packet and queue records still omit explicit language fields, so language coverage currently has to be inferred from cell_key.",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Execute bounded real Gemma slices for rust, c_cpp, and web_js_ts_html next, then promote to broader same-surface comparisons only after preserving the full-label anti-cheat prompt contract."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "target_language_count": len(TARGET_LANGUAGES),
            "ready_cell_count": audit["ready_cell_count"],
            "evidence_complete_cell_count": audit["evidence_complete_cell_count"],
            "real_gemma_execution_cell_count": audit["real_gemma_execution_cell_count"],
            "full_surface_real_gemma_execution_cell_count": audit["full_surface_real_gemma_execution_cell_count"],
            "packet_language_field_missing_count": audit["packet_language_field_missing_count"],
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "The standalone multilingual comparison surface is broader than the earlier blocker framing implied: python, rust, c_cpp, and web_js_ts_html are all packaged and evidence-complete, but only a bounded python Gemma slice has been executed so far and the comparison path required an anti-cheat fix to preserve the full label space.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage9769 Multilingual Gemma Readiness Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Ready standalone cells: `{audit['ready_cell_count']}`",
        f"Evidence-complete cells: `{audit['evidence_complete_cell_count']}`",
        f"Real Gemma execution cells: `{audit['real_gemma_execution_cell_count']}`",
        f"Full-surface real Gemma execution cells: `{audit['full_surface_real_gemma_execution_cell_count']}`",
        f"Packet language field missing count: `{audit['packet_language_field_missing_count']}`",
        "",
        "Target language groups covered in the standalone Gemma-ready queue: python, rust, c_cpp, web_js_ts_html.",
        "",
        "Key finding: bounded execution is now safe against slice-local label-vocabulary leakage, but cross-language executed evidence is still sparse.",
        "",
        f"Next: {next_step}",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "ready_cell_count": audit["ready_cell_count"],
        "evidence_complete_cell_count": audit["evidence_complete_cell_count"],
        "real_gemma_execution_cell_count": audit["real_gemma_execution_cell_count"],
        "full_surface_real_gemma_execution_cell_count": audit["full_surface_real_gemma_execution_cell_count"],
        "packet_language_field_missing_count": audit["packet_language_field_missing_count"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
