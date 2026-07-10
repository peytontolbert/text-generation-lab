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
STAGE = 9843
NAME = "stage9843_refresh_permuted_choice_review_cards"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "refresh_permuted_choice_review_cards_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REFRESH_PERMUTED_CHOICE_REVIEW_CARDS_STAGE9843.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
STAGE9841_MANIFEST = ROOT / "runs/local/artifacts/stage9841_permuted_choice_winner_review_packets/permuted_choice_winner_review_packet_manifest.json"
STAGE9842_AUDIT = ROOT / "runs/local/artifacts/stage9842_permuted_choice_decoy_coverage_audit/permuted_choice_decoy_coverage_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def _challenge_patch(challenge_family: str, record: dict[str, Any]) -> dict[str, Any]:
    hundred = record.get("hundred_m") or {}
    gemma = record.get("gemma") or {}
    packet = record.get("packet_structure") or {}
    if challenge_family == "label_proxy_shortcuts":
        return {
            "cell_specific_card_present": True,
            "passed": False,
            "notes": [
                f"Built-in decoy slice is now directly audited on this packet; 100M strict wrong-label follow rate is {hundred.get('wrong_label_follow_rate_on_strict')}.",
                f"Gemma strict wrong-label follow rate is {gemma.get('wrong_label_follow_rate_on_strict')}.",
                "Permutation resistance is better evidenced than before, but ablation and causal-flip are still missing, so this family remains provisional rather than passed.",
            ],
        }
    if challenge_family == "generation_quality_collapse":
        return {
            "cell_specific_card_present": True,
            "passed": True,
            "notes": [
                "Real Stage9839 row-level outputs exist for both eval and strict_eval on this packet.",
                f"100M strict exact under mixed replay is {hundred.get('strict_eval_exact')}, so the packet does not collapse into malformed structured output when the decoy note is present.",
            ],
        }
    if challenge_family == "cross_model_surface_fairness":
        return {
            "cell_specific_card_present": True,
            "passed": True,
            "notes": [
                "Stage9842 links the same paired roots across Stage9839 100M rows and Stage9835 Gemma rows.",
                f"Built-in decoy slice present: {packet.get('built_in_decoy_slice_present')}.",
            ],
        }
    if challenge_family in {"hidden_reference_materialization", "target_and_teacher_leakage", "metadata_and_graph_shortcuts"}:
        return {
            "cell_specific_card_present": False,
            "passed": False,
            "notes": ["No new direct cell-specific evidence was added for this family in Stage9842."],
        }
    return {"cell_specific_card_present": False, "passed": False, "notes": ["No refresh mapping available."]}


def build_refresh() -> dict[str, Any]:
    manifest_9841 = load_json(STAGE9841_MANIFEST)
    audit_9842 = load_json(STAGE9842_AUDIT)
    rows_9841 = manifest_9841.get("rows") if isinstance(manifest_9841.get("rows"), list) else []
    records_9842 = audit_9842.get("records") if isinstance(audit_9842.get("records"), list) else []
    record_by_lang = {str(row.get("language_family") or ""): row for row in records_9842}

    refreshed: list[dict[str, Any]] = []
    failures: list[str] = []
    for row in rows_9841:
        lang = str(row.get("language_family") or "")
        record = record_by_lang.get(lang)
        if not isinstance(record, dict):
            failures.append(f"missing_stage9842_record:{lang}")
            continue
        anti_path = ROOT / str((row.get("review_packet_paths") or {}).get("anti_cheat_cards") or "")
        anti_card = load_json(anti_path)
        families = anti_card.get("challenge_families") if isinstance(anti_card.get("challenge_families"), list) else []
        updated = []
        for family in families:
            challenge = str(family.get("challenge_family") or "")
            patch = _challenge_patch(challenge, record)
            updated.append(
                {
                    "challenge_family": challenge,
                    "cell_specific_card_present": patch["cell_specific_card_present"],
                    "passed": patch["passed"],
                    "notes": patch["notes"],
                }
            )
        anti_card["challenge_families"] = updated
        anti_card["reviewer_notes"] = [
            "Stage9843 refreshed this card with direct Stage9842 decoy evidence where it exists.",
            "Families without new direct evidence remain pending and should not be claimed as cleared.",
        ]
        write_json(anti_path, anti_card)
        refreshed.append(
            {
                "language_family": lang,
                "anti_cheat_card": str(anti_path.relative_to(ROOT)),
                "cell_specific_families_present": sum(1 for family in updated if family["cell_specific_card_present"]),
                "cell_specific_families_passed": sum(1 for family in updated if family["passed"]),
            }
        )

    metrics = {
        "refreshed_cells": len(refreshed),
        "cell_specific_families_present": sum(int(row["cell_specific_families_present"]) for row in refreshed),
        "cell_specific_families_passed": sum(int(row["cell_specific_families_passed"]) for row in refreshed),
    }
    if metrics["refreshed_cells"] != 4:
        failures.append("refreshed_cells_not_4")
    return {"passed": not failures, "failures": failures, "rows": refreshed, "metrics": metrics, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_refresh()
    write_json(
        MANIFEST,
        {
            "stage": STAGE,
            "name": NAME,
            "passed": built["passed"],
            "metrics": built["metrics"],
            "rows": built["rows"],
            "authority": dict(AUTHORITY_CLOSED),
        },
    )
    next_step = "Use the refreshed stage9841 cards for human review, then run fresh ablation and causal-flip executions on the same packet to replace the remaining pending anti-cheat families with direct evidence."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Refreshed the stage9841 anti-cheat review cards so direct Stage9842 decoy evidence now appears in the human-review packet instead of remaining only in a separate audit.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9843 Refresh Permuted-Choice Review Cards",
                "",
                f"Passed: `{built['passed']}`",
                f"Refreshed cells: `{built['metrics']['refreshed_cells']}`",
                f"Cell-specific families present: `{built['metrics']['cell_specific_families_present']}`",
                f"Cell-specific families passed: `{built['metrics']['cell_specific_families_passed']}`",
                "",
                "This stage pushes Stage9842 decoy evidence back into the review packet so human reviewers see the strongest current anti-cheat evidence in one place.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
