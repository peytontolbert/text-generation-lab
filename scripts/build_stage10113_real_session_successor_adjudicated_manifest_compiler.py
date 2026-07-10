#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10113
NAME = "stage10113_real_session_successor_adjudicated_manifest_compiler"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "real_session_successor_adjudication_audit.json"
ADJUDICATED_MANIFEST = OUT_DIR / "real_session_successor_adjudicated_manifest.jsonl"
BLOCKED_ROWS = OUT_DIR / "real_session_successor_adjudication_blocked_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_SUCCESSOR_ADJUDICATED_MANIFEST_COMPILER_STAGE10113.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BRIDGE = ROOT / "runs/local/artifacts/stage10112_real_session_successor_claim_bridge_after_review_workbook/real_session_successor_claim_bridge_after_review_workbook.json"
REVIEW_ROOT = ROOT / "runs/local/artifacts/stage10111_real_session_successor_review_packets/review_packets"
COMPLETE_STATUSES = {"completed_human_review", "completed", "adjudicated"}
ABSTAIN_LABEL = "ABSTAIN_INSUFFICIENT_EVIDENCE"
RUBRIC_LINES = [
    "visible_evidence_supports_one_candidate",
    "candidate_set_is_maintainer_plausible",
    "raw_changed_path_list_not_exposed",
    "visible_snippets_are_sufficient_for_local_reasoning",
    "abstention_would_be_more_honest_if_evidence_is_insufficient",
]
ANTI_CHEAT_LINES = [
    "changed_path_signature_leakage",
    "candidate_position_or_id_bias",
    "template_specific_surface_prior",
    "cross_repo_analogue_surface_leakage",
    "review_scope_matches_prompt_visible_evidence_only",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def review_packet_dir(review_root: Path, row_id: str) -> Path:
    digest = hashlib.sha256(row_id.encode("utf-8")).hexdigest()[:16]
    prefix = row_id.replace("::", "__").replace("/", "_")[:80]
    safe = f"{prefix}__{digest}"
    return review_root / safe


def _all_bool_fields(payload: dict[str, Any], keys: list[str]) -> bool:
    section = payload if isinstance(payload, dict) else {}
    return all(isinstance(section.get(key), bool) for key in keys)


def _validate_rubric(rubric: dict[str, Any], candidate_ids: set[str]) -> tuple[bool, list[str], dict[str, Any]]:
    reasons: list[str] = []
    status = str(rubric.get("status") or "")
    gold = rubric.get("gold_label_slot") if isinstance(rubric.get("gold_label_slot"), dict) else {}
    rubric_lines = rubric.get("rubric_lines") if isinstance(rubric.get("rubric_lines"), dict) else {}
    selected_candidate_id = gold.get("selected_candidate_id")
    abstain = gold.get("abstain_due_to_insufficient_evidence")
    rationale = str(gold.get("reviewer_rationale") or "").strip()
    passed = rubric.get("passed") is True

    if status not in COMPLETE_STATUSES:
        reasons.append("expert_review_incomplete")
    if not _all_bool_fields(rubric_lines, RUBRIC_LINES):
        reasons.append("expert_rubric_lines_incomplete")
    if not rationale:
        reasons.append("expert_rationale_missing")
    if passed:
        if not isinstance(abstain, bool):
            reasons.append("expert_abstain_flag_missing")
        if abstain is True and selected_candidate_id is not None:
            reasons.append("expert_abstain_and_candidate_both_set")
        if abstain is False and selected_candidate_id not in candidate_ids:
            reasons.append("expert_selected_candidate_invalid")
        if abstain is True and rubric_lines.get("abstention_would_be_more_honest_if_evidence_is_insufficient") is not True:
            reasons.append("expert_abstain_without_rubric_support")
    else:
        reasons.append("expert_review_not_passed")

    resolved_label = None
    if passed and not reasons:
        resolved_label = ABSTAIN_LABEL if abstain else str(selected_candidate_id)

    return not reasons, reasons, {
        "passed": passed,
        "resolved_label": resolved_label,
        "abstain_due_to_insufficient_evidence": abstain,
        "reviewer_rationale": rationale,
        "rubric_lines": rubric_lines,
    }


def _validate_anti_cheat(card: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    reasons: list[str] = []
    status = str(card.get("status") or "")
    passed = card.get("passed") is True
    challenge_lines = card.get("challenge_lines") if isinstance(card.get("challenge_lines"), dict) else {}
    notes = str(card.get("reviewer_notes") or "").strip()

    if status not in COMPLETE_STATUSES:
        reasons.append("anti_cheat_review_incomplete")
    if not _all_bool_fields(challenge_lines, ANTI_CHEAT_LINES):
        reasons.append("anti_cheat_lines_incomplete")
    if not notes:
        reasons.append("anti_cheat_notes_missing")
    if not passed:
        reasons.append("anti_cheat_review_not_passed")

    return not reasons, reasons, {
        "passed": passed,
        "reviewer_notes": notes,
        "challenge_lines": challenge_lines,
    }


def compile_adjudications(
    *,
    bridge_artifact: Path = BRIDGE,
    review_root: Path = REVIEW_ROOT,
    adjudicated_manifest_path: Path = ADJUDICATED_MANIFEST,
    blocked_rows_path: Path = BLOCKED_ROWS,
    audit_path: Path = AUDIT,
    expected_bridge_rows: int | None = 41,
) -> dict[str, Any]:
    bridge = load_json(bridge_artifact)
    bridge_rows = bridge.get("records") if isinstance(bridge.get("records"), list) else []
    failures: list[str] = []
    if bridge.get("passed") is not True:
        failures.append("stage10112_bridge_not_passed")

    adjudicated_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []

    for row in bridge_rows:
        row_id = str(row.get("row_id") or "")
        packet_dir = review_packet_dir(review_root, row_id)
        rubric_path = packet_dir / "expert_maintainer_rubric_review.json"
        anti_cheat_path = packet_dir / "anti_cheat_review_card.json"
        candidate_ids = {
            str(candidate.get("candidate_id"))
            for candidate in (((row.get("prompt_surface") or {}).get("candidate_choices")) or [])
            if candidate.get("candidate_id") is not None
        }
        row_reasons: list[str] = []
        rubric = load_json(rubric_path)
        anti_cheat = load_json(anti_cheat_path)
        if not rubric_path.exists():
            row_reasons.append("expert_review_file_missing")
        if not anti_cheat_path.exists():
            row_reasons.append("anti_cheat_review_file_missing")

        rubric_ok = False
        rubric_info: dict[str, Any] = {}
        anti_cheat_ok = False
        anti_cheat_info: dict[str, Any] = {}
        if rubric_path.exists():
            rubric_ok, rubric_reasons, rubric_info = _validate_rubric(rubric, candidate_ids)
            row_reasons.extend(rubric_reasons)
        if anti_cheat_path.exists():
            anti_cheat_ok, anti_cheat_reasons, anti_cheat_info = _validate_anti_cheat(anti_cheat)
            row_reasons.extend(anti_cheat_reasons)

        if rubric_ok and anti_cheat_ok:
            adjudicated_rows.append(
                {
                    "row_id": row_id,
                    "episode_id": row.get("episode_id"),
                    "repo_id": row.get("repo_id"),
                    "language_family": row.get("language_family"),
                    "successor_template": row.get("successor_template"),
                    "prompt_surface": row.get("prompt_surface"),
                    "hidden_metadata": row.get("hidden_metadata"),
                    "gold_answer": rubric_info["resolved_label"],
                    "gold_answer_kind": "abstain" if rubric_info["resolved_label"] == ABSTAIN_LABEL else "candidate_id",
                    "training_scoring_contract": {
                        "eligible_for_training_or_scoring": True,
                        "requires_abstention_support": rubric_info["resolved_label"] == ABSTAIN_LABEL,
                    },
                    "review_provenance": {
                        "expert_maintainer_rubric_review": display(rubric_path),
                        "cell_specific_anti_cheat_review": display(anti_cheat_path),
                        "review_workbook_path": row.get("review_workbook_path"),
                    },
                    "adjudication_notes": {
                        "expert_rationale": rubric_info["reviewer_rationale"],
                        "anti_cheat_notes": anti_cheat_info["reviewer_notes"],
                    },
                }
            )
        else:
            blocked_rows.append(
                {
                    "row_id": row_id,
                    "language_family": row.get("language_family"),
                    "successor_template": row.get("successor_template"),
                    "claim_status": row.get("claim_status"),
                    "block_reasons": sorted(set(row_reasons)),
                    "review_packet_dir": display(packet_dir),
                    "expert_maintainer_rubric_review": display(rubric_path),
                    "anti_cheat_review_card": display(anti_cheat_path),
                }
            )

    metrics = {
        "bridge_rows": len(bridge_rows),
        "adjudicated_rows": len(adjudicated_rows),
        "blocked_rows": len(blocked_rows),
        "rows_ready_for_training_or_scoring": len(adjudicated_rows),
        "rows_blocked_pending_or_failing_review": len(blocked_rows),
        "rows_with_abstain_gold_answer": sum(1 for row in adjudicated_rows if row["gold_answer"] == ABSTAIN_LABEL),
        "rows_with_candidate_gold_answer": sum(1 for row in adjudicated_rows if row["gold_answer"] != ABSTAIN_LABEL),
    }
    if expected_bridge_rows is not None and len(bridge_rows) != expected_bridge_rows:
        failures.append(f"stage10112_bridge_rows_not_{expected_bridge_rows}")

    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "metrics": metrics,
        "failures": failures,
        "claim_boundary": {
            "supports_training_or_scoring_now": len(adjudicated_rows) > 0 and len(blocked_rows) == 0 and not failures,
            "expert_maintainer_signoff_complete": len(blocked_rows) == 0,
            "anti_cheat_signoff_complete": len(blocked_rows) == 0,
        },
    }
    write_json(audit_path, audit)
    write_jsonl(adjudicated_manifest_path, adjudicated_rows)
    write_jsonl(blocked_rows_path, blocked_rows)
    return {
        "audit": audit,
        "adjudicated_rows": adjudicated_rows,
        "blocked_rows": blocked_rows,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = compile_adjudications()
    audit = built["audit"]
    next_step = "Complete the stage10111 rubric and anti-cheat review files, then rerun this compiler so only fully adjudicated successor rows enter the manifest used for training, scoring, or Gemma comparison."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "metrics": {**audit["metrics"], "failures": audit["failures"]},
        "artifacts": {
            "audit": display(AUDIT),
            "adjudicated_manifest": display(ADJUDICATED_MANIFEST),
            "blocked_rows": display(BLOCKED_ROWS),
            "doc": display(DOC),
        },
        "decision": "Compiled the successor review-packet contract into a machine-usable adjudication gate so only rows with completed expert rubric, completed anti-cheat review, and an explicit gold answer can enter training or scoring.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10113 Real Session Successor Adjudicated Manifest Compiler",
                "",
                f"Passed: `{summary['passed']}`",
                f"Bridge rows: `{audit['metrics']['bridge_rows']}`",
                f"Adjudicated rows: `{audit['metrics']['adjudicated_rows']}`",
                f"Blocked rows: `{audit['metrics']['blocked_rows']}`",
                "",
                summary["decision"],
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
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": audit["metrics"], "failures": audit["failures"], "next_best_step": next_step}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
