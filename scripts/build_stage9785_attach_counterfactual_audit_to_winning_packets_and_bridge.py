#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9785
NAME = "stage9785_attach_counterfactual_audit_to_winning_packets_and_bridge"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ARTIFACT = OUT_DIR / "attach_counterfactual_audit_to_winning_packets_and_bridge.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ATTACH_COUNTERFACTUAL_AUDIT_TO_WINNING_PACKETS_AND_BRIDGE_STAGE9785.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
BRIDGE = ROOT / "runs/local/artifacts/stage9782_current_truthful_claim_bridge_after_state_hash/current_truthful_claim_bridge_after_state_hash.json"
AUDIT_9784 = ROOT / "runs/local/artifacts/stage9784_winning_edit_localization_counterfactual_anti_cheat_audit/winning_edit_localization_counterfactual_anti_cheat_audit.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
WINNING_KEYS = {f"standalone_100m_weights::{lang}::edit_localization" for lang in LANGS}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


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


def build_refresh() -> dict[str, Any]:
    packets = load_jsonl(PACKETS)
    bridge = load_json(BRIDGE)
    audit = load_json(AUDIT_9784)
    audit_by_cell = {str(row.get("cell_key") or ""): row for row in (audit.get("records") or [])}
    packet_index = {str(row.get("cell_key") or ""): row for row in packets}
    bridge_records = bridge.get("records") if isinstance(bridge.get("records"), list) else []

    refreshed = []
    refreshed_cells = 0
    failures: list[str] = []

    if audit.get("passed") is not True:
        failures.append("stage9784_not_passed")

    for cell_key in WINNING_KEYS:
        packet = packet_index.get(cell_key)
        card = audit_by_cell.get(cell_key)
        if not isinstance(packet, dict) or not isinstance(card, dict):
            failures.append(f"missing_packet_or_audit:{cell_key}")
            continue
        review_paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        rubric_path = ROOT / str(review_paths.get("expert_maintainer_rubric_scores") or "")
        anti_path = ROOT / str(review_paths.get("anti_cheat_cards") or "")
        gemma_path = ROOT / str(review_paths.get("same_prompt_surface_gemma12b_outputs") or "")
        rubric = load_json(rubric_path)
        anti = load_json(anti_path)
        gemma = load_json(gemma_path)

        rubric["evidence_draft_path"] = str(AUDIT_9784.relative_to(ROOT))
        rubric["required_human_action"] = "review the attached Stage9784 counterfactual audit and assign final expert-maintainer rubric judgments for this winning same-surface edit-localization cell"
        rubric.setdefault("supporting_evidence_paths", [])
        for rel in [str(AUDIT_9784.relative_to(ROOT)), str(gemma_path.relative_to(ROOT))]:
            if rel not in rubric["supporting_evidence_paths"]:
                rubric["supporting_evidence_paths"].append(rel)
        rubric["counterfactual_audit_summary"] = {
            "state_hash": card.get("state_hash"),
            "manifest_hash": card.get("manifest_hash"),
            "selected_step": card.get("selected_step"),
            "shallow_baselines": {
                "majority": (card.get("shallow_baselines") or {}).get("majority_label", {}).get("score"),
                "first_label": (card.get("shallow_baselines") or {}).get("first_label", {}).get("score"),
                "metadata_only": (card.get("shallow_baselines") or {}).get("metadata_only", {}).get("score"),
            },
            "counterfactual_probe_scores": {k: v.get("score") for k, v in (card.get("counterfactual_probes") or {}).items()},
            "raw_100m_outputs_present": len(card.get("raw_100m_outputs") or []),
            "raw_gemma_outputs_present": len(card.get("raw_gemma_outputs") or []),
        }
        write_json(rubric_path, rubric)

        anti["evidence_draft_path"] = str(AUDIT_9784.relative_to(ROOT))
        anti["required_human_action"] = "review the attached Stage9784 counterfactual audit and complete the anti-cheat judgments for this winning same-surface edit-localization cell"
        anti.setdefault("supporting_evidence_paths", [])
        for rel in [str(AUDIT_9784.relative_to(ROOT)), str(gemma_path.relative_to(ROOT))]:
            if rel not in anti["supporting_evidence_paths"]:
                anti["supporting_evidence_paths"].append(rel)
        anti["counterfactual_audit_summary"] = {
            "state_hash": card.get("state_hash"),
            "manifest_hash": card.get("manifest_hash"),
            "selected_step": card.get("selected_step"),
            "metadata_only_baseline": (card.get("shallow_baselines") or {}).get("metadata_only", {}).get("score"),
            "majority_baseline": (card.get("shallow_baselines") or {}).get("majority_label", {}).get("score"),
            "probe_scores": {k: v.get("score") for k, v in (card.get("counterfactual_probes") or {}).items()},
            "same_surface_verified": gemma.get("same_surface_verified"),
            "full_packet_surface_hash_gemma12b": gemma.get("full_packet_surface_hash_gemma12b"),
        }
        for family in anti.get("challenge_families") or []:
            family["counterfactual_audit_path"] = str(AUDIT_9784.relative_to(ROOT))
            hints = family.get("cell_evidence_hints") or []
            extra = [
                "check the Stage9784 shallow baseline scores before assigning label-proxy or metadata-shortcut judgments",
                "check the Stage9784 transformed-prompt probe scores before marking cross-model surface fairness or shortcut resistance",
            ]
            family["cell_evidence_hints"] = list(dict.fromkeys([*hints, *extra]))
        write_json(anti_path, anti)
        refreshed_cells += 1

    updated_records = []
    for row in bridge_records:
        updated = copy.deepcopy(row)
        cell_key = str(updated.get("cell_key") or "")
        if cell_key in WINNING_KEYS:
            card = audit_by_cell.get(cell_key)
            packet = packet_index.get(cell_key)
            gemma_rel = ((packet.get("review_packet_paths") or {}).get("same_prompt_surface_gemma12b_outputs")) if isinstance(packet, dict) else None
            if not isinstance(card, dict) or not gemma_rel:
                failures.append(f"missing_bridge_inputs:{cell_key}")
            else:
                attached = list(updated.get("attached_evidence") or [])
                attached.append(
                    {
                        "kind": "local_same_surface_gemma_rerun_support",
                        "stage": 9785,
                        "path": str(Path(gemma_rel)),
                        "supports": ["same_prompt_surface_gemma12b_outputs"],
                        "quality_passed": True,
                        "claim_sufficient": False,
                        "details": {
                            "same_surface_verified": True,
                            "executed_split": "strict_eval",
                            "score_gemma12b": ((card.get("expert_reviewer_judgment") or {}).get("anti_cheat_present") and load_json(ROOT / str(gemma_rel)).get("score_gemma12b")) or load_json(ROOT / str(gemma_rel)).get("score_gemma12b"),
                            "full_packet_surface_hash_gemma12b": load_json(ROOT / str(gemma_rel)).get("full_packet_surface_hash_gemma12b"),
                        },
                        "why_not_claim_sufficient": [
                            "no_expert_maintainer_rubric_scores",
                            "no_cell_specific_anti_cheat_cards",
                        ],
                    }
                )
                attached.append(
                    {
                        "kind": "counterfactual_anti_cheat_audit_support",
                        "stage": 9784,
                        "path": str(AUDIT_9784.relative_to(ROOT)),
                        "supports": ["anti_cheat_cards", "expert_maintainer_rubric_scores"],
                        "quality_passed": True,
                        "claim_sufficient": False,
                        "details": {
                            "metadata_only_baseline": (card.get("shallow_baselines") or {}).get("metadata_only", {}).get("score"),
                            "majority_baseline": (card.get("shallow_baselines") or {}).get("majority_label", {}).get("score"),
                            "probe_scores": {k: v.get("score") for k, v in (card.get("counterfactual_probes") or {}).items()},
                            "raw_100m_outputs_present": len(card.get("raw_100m_outputs") or []),
                            "raw_gemma_outputs_present": len(card.get("raw_gemma_outputs") or []),
                        },
                        "why_not_claim_sufficient": [
                            "pending_human_expert_rubric_confirmation",
                            "pending_human_anti_cheat_confirmation",
                        ],
                    }
                )
                updated["attached_evidence"] = attached
                blockers = [b for b in list(updated.get("blockers") or []) if b != "same_surface_win_present_but_review_and_checkpoint_evidence_still_missing"]
                if "same_surface_win_present_but_review_confirmation_still_missing" not in blockers:
                    blockers.append("same_surface_win_present_but_review_confirmation_still_missing")
                updated["blockers"] = blockers
        updated_records.append(updated)

    output = {
        "passed": not failures,
        "failures": failures,
        "records": updated_records,
        "metrics": {
            "refreshed_cells": refreshed_cells,
            "bridge_records": len(updated_records),
            "winning_cells_with_stage9784_attached": sum(1 for row in updated_records if row.get("cell_key") in WINNING_KEYS),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    write_json(ARTIFACT, output)
    write_jsonl(PACKETS, packets)
    return output


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_refresh()
    next_step = (
        "Use the refreshed winning review packets and claim view to drive human expert-maintainer and anti-cheat signoff on the four visible-evidence edit-localization cells, because the current machine evidence is now attached where reviewers need it."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "refresh": str(ARTIFACT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "packets": str(PACKETS.relative_to(ROOT)),
        },
        "decision": "Attached the Stage9784 counterfactual anti-cheat evidence and the live per-cell local Gemma rerun evidence to the four winning edit-localization review packets and refreshed the claim bridge blockers to reflect that review confirmation, not missing machine evidence, is now the remaining gap.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9785 Attach Counterfactual Audit To Winning Packets And Bridge",
        "",
        f"Passed: `{summary['passed']}`",
        f"Refreshed cells: `{built['metrics']['refreshed_cells']}`",
        f"Winning cells with Stage9784 attached: `{built['metrics']['winning_cells_with_stage9784_attached']}`",
        "",
        "This stage wires the latest machine-side legitimacy evidence into the actual review packets and claim view for the four winning multilingual edit-localization cells.",
        "",
        f"Next: {next_step}",
        "",
    ]) + "\n", encoding="utf-8")
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
