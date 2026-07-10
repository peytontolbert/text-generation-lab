#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9718
NAME = "stage9718_locked_multilingual_acceptance_evidence_ledger"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage9684_v27_multilingual_eval_acceptance_contract/v27_multilingual_eval_acceptance_contract.json"
SOURCE_PACKS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_multilingual_task_pack_skeleton.json"
SOURCE_ANTI_HACK = ROOT / "runs/summaries/stage9717_locked_multilingual_eval_hacking_audit.json"
SOURCE_SYMBOL_BINDING_PROBE = ROOT / "runs/summaries/stage9698_symbol_binding_target_100m_structured_tiny_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "locked_multilingual_acceptance_evidence_ledger.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_LOCKED_MULTILINGUAL_ACCEPTANCE_EVIDENCE_LEDGER_STAGE9718.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def expected_evidence(contract: dict[str, Any], mode: str) -> list[str]:
    mapping = contract.get("required_evidence_by_mode") or {}
    values = mapping.get(mode) if isinstance(mapping, dict) else []
    return [str(value) for value in values or []]


def seed_evidence(pack: dict[str, Any], symbol_binding_probe: dict[str, Any]) -> list[dict[str, Any]]:
    mode = str(pack.get("mode") or "")
    skill = str(pack.get("skill_area") or "")
    if mode != "standalone_100m_weights" or skill != "symbol_binding":
        return []
    if symbol_binding_probe.get("passed") is not True:
        return []
    metrics = symbol_binding_probe.get("metrics") if isinstance(symbol_binding_probe.get("metrics"), dict) else {}
    return [
        {
            "kind": "target_100m_structured_probe_support",
            "stage": 9698,
            "path": str(SOURCE_SYMBOL_BINDING_PROBE.relative_to(ROOT)),
            "supports": [
                "standalone_generation_or_structured_action_outputs",
                "telemetry_bundle",
            ],
            "quality_passed": symbol_binding_probe.get("quality_passed") is True,
            "details": {
                "estimated_parameter_count": metrics.get("estimated_parameter_count"),
                "eval_symbol_binding_exact": metrics.get("eval_symbol_binding_exact"),
                "strict_symbol_binding_exact": metrics.get("strict_symbol_binding_exact"),
                "forbidden_runtime_executed": metrics.get("forbidden_runtime_executed"),
            },
            "claim_sufficient": False,
            "why_not_claim_sufficient": [
                "no_same_surface_gemma12b_outputs",
                "no_language_slice_scores",
                "no_expert_maintainer_rubric_scores",
                "probe_quality_not_passing_acceptance",
            ],
        }
    ]


def build_record(
    pack: dict[str, Any],
    contract: dict[str, Any],
    anti_hack_summary: dict[str, Any],
    symbol_binding_probe: dict[str, Any],
) -> dict[str, Any]:
    mode = str(pack.get("mode") or "")
    expected = expected_evidence(contract, mode)
    evidence = seed_evidence(pack, symbol_binding_probe)
    seeded_support = {item for row in evidence for item in row.get("supports", [])}
    missing_required_evidence = [item for item in expected if item not in seeded_support]
    blockers = [
        "stage9717_locked_anti_eval_hacking_gate_must_pass",
        "same_surface_100m_vs_gemma12b_evidence_missing",
        "expert_maintainer_rubric_scores_missing",
        "anti_cheat_cards_not_attached_for_specific_cell",
    ]
    blockers.extend(f"missing_required_evidence:{item}" for item in missing_required_evidence)
    if mode == "full_product_harness":
        blockers.append("harness_run_not_recorded")
    else:
        blockers.append("standalone_language_slice_scores_missing")
    if str(pack.get("skill_area") or "") == "symbol_binding" and evidence:
        blockers.append("symbol_binding_probe_is_supporting_only_not_acceptance_quality")
    return {
        "task_pack_id": pack.get("task_pack_id"),
        "source_id": pack.get("source_id"),
        "lineage_hash": pack.get("lineage_hash"),
        "cell_key": "::".join([
            mode,
            str(pack.get("language_family") or ""),
            str(pack.get("skill_area") or ""),
        ]),
        "mode": mode,
        "language_family": str(pack.get("language_family") or ""),
        "skill_area": str(pack.get("skill_area") or ""),
        "required_evidence": expected,
        "attached_evidence": evidence,
        "missing_required_evidence": missing_required_evidence,
        "anti_hacking_gate_stage": 9717,
        "anti_hacking_gate_passed": anti_hack_summary.get("passed") is True,
        "claim_ready": False,
        "claim_status": "blocked_missing_final_evidence",
        "blockers": blockers,
        "authority": dict(AUTHORITY_CLOSED),
    }


def build_ledger(
    contract: dict[str, Any],
    packs: list[dict[str, Any]],
    anti_hack_summary: dict[str, Any],
    symbol_binding_probe: dict[str, Any],
) -> dict[str, Any]:
    records = [
        build_record(pack, contract, anti_hack_summary, symbol_binding_probe)
        for pack in packs
    ]
    claim_ready = [record for record in records if record.get("claim_ready") is True]
    status_counts = Counter(str(record.get("claim_status") or "unknown") for record in records)
    mode_counts = Counter(str(record.get("mode") or "") for record in records)
    language_counts = Counter(str(record.get("language_family") or "") for record in records)
    skill_counts = Counter(str(record.get("skill_area") or "") for record in records)
    seeded_supporting = [
        record["cell_key"]
        for record in records
        if record.get("attached_evidence")
    ]
    failures: list[str] = []
    if anti_hack_summary.get("passed") is not True:
        failures.append("stage9717_not_passed")
    if len(records) != len(packs):
        failures.append("ledger_record_count_mismatch")
    if claim_ready:
        failures.append("unexpected_claim_ready_cells")
    if len(seeded_supporting) != 4:
        failures.append("expected_only_four_symbol_binding_support_cells_seeded")
    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "metrics": {
            "records": len(records),
            "claim_ready_cells": len(claim_ready),
            "blocked_cells": len(records) - len(claim_ready),
            "status_counts": dict(sorted(status_counts.items())),
            "mode_counts": dict(sorted(mode_counts.items())),
            "language_counts": dict(sorted(language_counts.items())),
            "skill_counts": dict(sorted(skill_counts.items())),
            "seeded_supporting_evidence_cells": sorted(seeded_supporting),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    contract = load_json(SOURCE_CONTRACT)
    suite = load_json(SOURCE_PACKS)
    anti_hack_summary = load_json(SOURCE_ANTI_HACK)
    symbol_binding_probe = load_json(SOURCE_SYMBOL_BINDING_PROBE)
    packs = suite.get("benchmark_packs") if isinstance(suite, dict) else []
    if not isinstance(packs, list):
        packs = []
    ledger = build_ledger(contract, packs, anti_hack_summary, symbol_binding_probe)
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Attach same-surface Gemma-12B outputs, language-slice scores, expert-maintainer rubric scores, and "
        "cell-specific anti-cheat cards into the Stage9718 ledger before claiming any acceptance cell."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": ledger["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **(ledger.get("metrics") or {}),
        },
        "artifacts": {
            "ledger": str(LEDGER.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized the canonical locked multilingual acceptance evidence ledger and seeded supporting pre-comparison evidence without making any completion claim.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9718 Locked Multilingual Acceptance Evidence Ledger",
        "",
        f"Passed: `{summary['passed']}`",
        f"Records: `{summary['metrics']['records']}`",
        f"Claim-ready cells: `{summary['metrics']['claim_ready_cells']}`",
        f"Seeded supporting evidence cells: `{summary['metrics']['seeded_supporting_evidence_cells']}`",
        "",
        "This stage creates the canonical per-cell evidence ledger for the final v2.7 objective. It is intentionally strict: seeded supporting probe evidence does not become a claim-ready acceptance cell without same-surface Gemma evidence, expert rubric results, and attached anti-cheat cards.",
        "",
        "No Gemma, harness, runtime, scoring, training, source/body emission, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": ledger["failures"],
        "records": summary["metrics"]["records"],
        "claim_ready_cells": summary["metrics"]["claim_ready_cells"],
        "seeded_supporting_evidence_cells": summary["metrics"]["seeded_supporting_evidence_cells"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if ledger["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
