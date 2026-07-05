#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8896
NAME = "stage8896_next_stage_allocation_preflight"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NEXT_STAGE_ALLOCATION_PREFLIGHT_STAGE8896.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
RESERVED_STAGES = {8890}
PROTECTED_STAGE_MIN = 8880

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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def next_free_stage(used: set[int], *, start: int) -> int:
    stage = start
    while stage in used or stage in RESERVED_STAGES:
        stage += 1
    return stage


def allocation_preflight(registry: dict[str, Any], *, current_stage: int = STAGE) -> dict[str, Any]:
    rows = list(registry.get("rows") or [])
    used = {int(row.get("stage", -1)) for row in rows if str(row.get("stage", "")).lstrip("-").isdigit()}
    latest_stage = int((registry.get("metrics") or {}).get("latest_stage", -1))
    max_stage = max(used or {-1})
    allocated_stage = next_free_stage(used | {current_stage}, start=current_stage + 1)
    occupied_reserved = sorted(stage for stage in RESERVED_STAGES if stage in used)
    future_summary = ROOT / "runs/summaries" / f"stage{allocated_stage}_<name>.json"
    future_script = ROOT / "scripts" / f"build_stage{allocated_stage}_<name>.py"
    future_doc = ROOT / "docs" / f"<NAME>_STAGE{allocated_stage}.md"
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    failures: list[str] = []
    if latest_stage not in {current_stage - 1, current_stage}:
        failures.append(f"unexpected_registry_frontier:{latest_stage}")
    if max_stage not in {current_stage - 1, current_stage}:
        failures.append(f"unexpected_registry_max_stage:{max_stage}")
    if occupied_reserved:
        failures.append(f"reserved_stage_occupied:{','.join(map(str, occupied_reserved))}")
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "latest_stage_before_update": latest_stage,
        "max_stage_before_update": max_stage,
        "protected_stage_min": PROTECTED_STAGE_MIN,
        "reserved_stages": sorted(RESERVED_STAGES),
        "occupied_reserved_stages": occupied_reserved,
        "current_stage": current_stage,
        "allocated_next_free_stage": allocated_stage,
        "future_artifact_templates": {
            "summary": str(future_summary.relative_to(ROOT)),
            "script": str(future_script.relative_to(ROOT)),
            "doc": str(future_doc.relative_to(ROOT)),
        },
        "registry_authority_counts_zero": not any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED),
    }


def main() -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = allocation_preflight(registry)
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            **audit,
            "authority_rows": 0,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
        },
        "decision": "Next-stage allocation preflight passed. Future no-execution builders should use the allocated next free stage and keep Stage8890 reserved." if audit["passed"] else "Next-stage allocation preflight failed.",
        "next_best_step": "Use allocated_next_free_stage for the next no-execution stage unless a newer registry frontier appears first; rerun allocation before writing if concurrent work advances the registry.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8896 Next Stage Allocation Preflight",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution preflight records the next safe stage number for future builders.",
        "",
        f"Allocated next free stage: `{audit['allocated_next_free_stage']}`",
        "",
        "Rules:",
        "",
        "- rerun this preflight if concurrent work advances the registry",
        "- keep reserved Stage8890 unmaterialized unless explicitly authorized",
        "- use unique summary/script/doc names for new stages",
        "- keep all authority counts closed unless a separate explicit authorization ticket says otherwise",
        "",
        "This opens no training, execution, decoder CE, denoise CE, runtime, mining, source/body emission, Gemma, harness, scoring, controller merge, checkpoint export, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "next_free_stage": audit["allocated_next_free_stage"],
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8896 Next Stage Allocation Preflight"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8896 adds a no-execution allocator for future stage numbers. It records the next free stage, keeps Stage8890 reserved, and requires rerunning allocation before writing if concurrent work advances the registry.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
