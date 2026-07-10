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

try:
    from build_stage9719_multilingual_comparison_evidence_bundle_contract import RUBRIC_SUBSKILLS
except ModuleNotFoundError:
    from scripts.build_stage9719_multilingual_comparison_evidence_bundle_contract import RUBRIC_SUBSKILLS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9983
NAME = "stage9983_gemma_advantage_row_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "gemma_advantage_row_review_packets.jsonl"
MANIFEST = OUT_DIR / "gemma_advantage_row_review_packet_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GEMMA_ADVANTAGE_ROW_REVIEW_PACKETS_STAGE9983.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage9982_gemma_advantage_review_packet/gemma_advantage_review_rows.jsonl"

CHALLENGE_FAMILIES = [
    "hidden_reference_materialization",
    "target_and_teacher_leakage",
    "label_proxy_shortcuts",
    "metadata_and_graph_shortcuts",
    "generation_quality_collapse",
    "cross_model_surface_fairness",
]

IN_SCOPE_SUBSKILLS = [
    "understands_user_intent",
    "retrieves_source_evidence_when_needed",
    "binds_symbols_correctly",
    "localizes_edit_scope",
    "repairs_or_abstains_safely",
    "avoids_hallucinated_symbols",
    "avoids_internal_tokens",
    "produces_contentful_final_answer",
]


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def packet_paths(row_id: str) -> dict[str, str]:
    slug = row_id.replace("::", "__").replace("/", "_")
    base = OUT_DIR / "review_packets" / slug
    return {
        "packet_dir": str(base.relative_to(ROOT)),
        "expert_maintainer_rubric_scores": str((base / "expert_maintainer_rubric_review.json").relative_to(ROOT)),
        "anti_cheat_cards": str((base / "anti_cheat_review_card.json").relative_to(ROOT)),
        "rubric_recommendation_draft": str((base / "expert_maintainer_recommendation_draft.json").relative_to(ROOT)),
        "anti_cheat_recommendation_draft": str((base / "anti_cheat_recommendation_draft.json").relative_to(ROOT)),
    }


def _counterfactual_role(row_id: str) -> str:
    if "::mixed_replay" in row_id:
        return "mixed_replay"
    if "::eval_replay" in row_id:
        return "positive_original_eval_replay"
    return "other"


def _has_decoy_text(row: dict[str, Any]) -> bool:
    text = f"{row.get('task_observation') or ''} {row.get('visible_locality_evidence') or ''}".lower()
    return "decoy" in text or "stale unrelated reviewer note" in text or "ignore irrelevant references" in text


def _scope_notes(row: dict[str, Any]) -> list[str]:
    notes = [
        "This row is a single opaque-choice edit-localization decision, not a full patch or verifier episode.",
        "Use human review to decide whether the visible evidence supports one justified answer, an abstention label, or multiple valid targets.",
    ]
    if _counterfactual_role(str(row.get("row_id") or "")) == "mixed_replay":
        notes.append("This row is a mixed-replay counterfactual variant with intentionally irrelevant decoy text.")
    if "no specific symbol is available" in str(row.get("visible_locality_evidence") or "").lower():
        notes.append("Visible evidence says no specific symbol is available, which may indicate abstention or set-valued scope rather than a singleton localization label.")
    return notes


def _rubric_draft(row: dict[str, Any]) -> dict[str, Any]:
    row_id = str(row.get("row_id") or "")
    role = _counterfactual_role(row_id)
    notes = _scope_notes(row)
    recommended: dict[str, dict[str, Any]] = {}
    for name in RUBRIC_SUBSKILLS:
        if name in IN_SCOPE_SUBSKILLS:
            rec = None
            confidence = "requires_human_confirmation"
            subskill_notes = list(notes)
            if name == "repairs_or_abstains_safely":
                subskill_notes.append("If the evidence is insufficient or underdetermined, the correct expert-maintainer judgment may be abstain rather than a forced singleton label.")
            if name == "localizes_edit_scope" and role == "mixed_replay":
                subskill_notes.append("Mixed-replay decoy text makes this row a direct identifiability test rather than a pure localization success row.")
            recommended[name] = {
                "recommended_judgment": rec,
                "confidence": confidence,
                "reviewer_notes": subskill_notes,
            }
        else:
            recommended[name] = {
                "recommended_judgment": None,
                "confidence": "out_of_scope_for_this_row",
                "reviewer_notes": ["This row does not exercise this maintainer rubric line directly."],
            }
    return {
        "row_id": row_id,
        "language_family": row.get("language_family"),
        "same_surface_prediction": row.get("pred"),
        "same_surface_target": row.get("target"),
        "counterfactual_role": role,
        "recommended_subskills": recommended,
        "reviewer_message": "Use this draft only to focus human review on identifiability, abstention, and shortcut risk. Do not treat it as final signoff.",
        "authority": dict(AUTHORITY_CLOSED),
    }


def _anti_draft(row: dict[str, Any]) -> dict[str, Any]:
    row_id = str(row.get("row_id") or "")
    role = _counterfactual_role(row_id)
    has_decoy = _has_decoy_text(row)
    small_margin = float(row.get("margin") or 0.0) < 0.01
    judgments = []
    for family in CHALLENGE_FAMILIES:
        recommended = None
        confidence = "requires_human_confirmation"
        notes: list[str] = []
        if family == "hidden_reference_materialization":
            notes = ["Review the row payload and confirm that no hidden source row ID, gold label text, or leaked teacher output is visible to the model."]
        elif family == "target_and_teacher_leakage":
            recommended = True
            confidence = "medium"
            notes = ["The row packet only exposes opaque choices plus evidence text, not Gemma output or the gold label as free text."]
        elif family == "label_proxy_shortcuts":
            if role == "mixed_replay" or has_decoy:
                recommended = None
                confidence = "requires_human_confirmation"
                notes = [
                    "This row includes decoy or mixed-replay text and should be checked for whether the forced singleton label is still identifiable from causal evidence.",
                    f"Stage9980 margin was {float(row.get('margin') or 0.0):.6f}; low-margin failures are consistent with ambiguity or unstable shortcuts.",
                ]
            else:
                recommended = None
                confidence = "requires_human_confirmation"
                notes = ["Check whether the opaque choice remains justified without relying on position, template, or stable answer priors."]
        elif family == "metadata_and_graph_shortcuts":
            recommended = None
            confidence = "requires_human_confirmation"
            notes = ["Confirm the answer is not recoverable from template role, graph metadata, or candidate ordering alone."]
        elif family == "generation_quality_collapse":
            recommended = True
            confidence = "medium"
            notes = ["The model produced a valid opaque choice token rather than junk or internal tokens, so this row is not a free-form generation-collapse case."]
        elif family == "cross_model_surface_fairness":
            recommended = True
            confidence = "high"
            notes = ["This row came from a same-surface 100M-versus-Gemma comparison and should be reviewed as a paired fairness case, not as a single-model anecdote."]
        judgments.append({"challenge_family": family, "recommended_pass": recommended, "confidence": confidence, "reviewer_notes": notes})
    return {
        "row_id": row_id,
        "language_family": row.get("language_family"),
        "same_surface_prediction": row.get("pred"),
        "same_surface_target": row.get("target"),
        "counterfactual_role": role,
        "small_margin_failure": small_margin,
        "has_decoy_text": has_decoy,
        "recommended_challenge_judgments": judgments,
        "reviewer_message": "This draft exists to decide whether the row is a valid expert-maintainer eval item, an abstention case, or an eval-hack risk that should be quarantined.",
        "authority": dict(AUTHORITY_CLOSED),
    }


def build_packets() -> dict[str, Any]:
    source_rows = load_jsonl(SOURCE_ROWS)
    failures: list[str] = []
    packets: list[dict[str, Any]] = []
    python_rows = 0
    c_cpp_rows = 0
    mixed_rows = 0
    for row in source_rows:
        row_id = str(row.get("row_id") or "")
        if not row_id:
            failures.append("missing_row_id")
            continue
        paths = packet_paths(row_id)
        rubric_path = ROOT / paths["expert_maintainer_rubric_scores"]
        anti_path = ROOT / paths["anti_cheat_cards"]
        rubric_draft_path = ROOT / paths["rubric_recommendation_draft"]
        anti_draft_path = ROOT / paths["anti_cheat_recommendation_draft"]
        role = _counterfactual_role(row_id)
        if str(row.get("language_family") or "") == "python":
            python_rows += 1
        if str(row.get("language_family") or "") == "c_cpp":
            c_cpp_rows += 1
        if role == "mixed_replay":
            mixed_rows += 1
        rubric_stub = {
            "row_id": row_id,
            "language_family": row.get("language_family"),
            "split": row.get("split"),
            "surface": row.get("surface"),
            "status": "pending_human_review",
            "reviewer_must_confirm": True,
            "required_human_action": "Decide whether this row is a valid singleton localization item, an abstention case, or a row that should be quarantined from training and headline eval claims.",
            "rubric_version": "expert_maintainer_v1",
            "passed": False,
            "counterfactual_role": role,
            "task_observation": row.get("task_observation"),
            "visible_locality_evidence": row.get("visible_locality_evidence"),
            "candidate_choices": row.get("candidate_choices"),
            "same_surface_prediction": row.get("pred"),
            "same_surface_target": row.get("target"),
            "same_surface_correct": row.get("correct"),
            "subskills": {name: None for name in RUBRIC_SUBSKILLS},
            "in_scope_subskills": IN_SCOPE_SUBSKILLS,
            "out_of_scope_subskills": [name for name in RUBRIC_SUBSKILLS if name not in IN_SCOPE_SUBSKILLS],
            "failure_trace_refs": [],
            "reviewer_notes": [],
            "supporting_evidence_paths": {
                "row_packet": display(SOURCE_ROWS),
                "stage9980_logits": "runs/local/artifacts/stage9980_selective_gemma_advantage_target100m_probe/edit_localization_probe/row_field_logits.jsonl",
                "stage9981_outcome_audit": "runs/local/artifacts/stage9981_selective_replay_outcome_audit/selective_replay_outcome_audit.json",
            },
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_stub = {
            "row_id": row_id,
            "language_family": row.get("language_family"),
            "split": row.get("split"),
            "surface": row.get("surface"),
            "status": "pending_cell_specific_review",
            "passed": False,
            "must_pass_global_stage9717_gate": True,
            "counterfactual_role": role,
            "task_observation": row.get("task_observation"),
            "visible_locality_evidence": row.get("visible_locality_evidence"),
            "candidate_choices": row.get("candidate_choices"),
            "same_surface_prediction": row.get("pred"),
            "same_surface_target": row.get("target"),
            "same_surface_correct": row.get("correct"),
            "challenge_families": [{"challenge_family": family, "present": False, "recommended_pass": None, "reviewer_notes": []} for family in CHALLENGE_FAMILIES],
            "reviewer_notes": [],
            "supporting_evidence_paths": rubric_stub["supporting_evidence_paths"],
            "authority": dict(AUTHORITY_CLOSED),
        }
        write_json(rubric_path, rubric_stub)
        write_json(anti_path, anti_stub)
        write_json(rubric_draft_path, _rubric_draft(row))
        write_json(anti_draft_path, _anti_draft(row))
        packets.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "split": row.get("split"),
                "surface": row.get("surface"),
                "counterfactual_role": role,
                "same_surface_prediction": row.get("pred"),
                "same_surface_target": row.get("target"),
                "same_surface_correct": row.get("correct"),
                "review_packet_paths": paths,
                "task_observation": row.get("task_observation"),
                "visible_locality_evidence": row.get("visible_locality_evidence"),
            }
        )
    metrics = {
        "review_rows": len(packets),
        "python_rows": python_rows,
        "c_cpp_rows": c_cpp_rows,
        "mixed_replay_rows": mixed_rows,
        "all_rows_incorrect": all(not bool(row.get("same_surface_correct")) for row in packets),
    }
    if metrics["review_rows"] != 11:
        failures.append("review_rows_not_11")
    if metrics["python_rows"] != 6:
        failures.append("python_rows_not_6")
    if metrics["c_cpp_rows"] != 5:
        failures.append("c_cpp_rows_not_5")
    if not metrics["all_rows_incorrect"]:
        failures.append("expected_all_rows_incorrect")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": packets, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packets()
    write_jsonl(PACKETS, built["rows"])
    write_json(MANIFEST, {"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "rows": built["rows"], "authority": dict(AUTHORITY_CLOSED)})
    next_step = (
        "Work these 11 row-level packets as explicit expert-maintainer and anti-cheat signoff items, then quarantine, abstention-relabeled, "
        "or keep-in-eval each row before it is reused for v2.7 training or headline 100M-versus-Gemma claims."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packets": display(PACKETS), "manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Materialized per-row expert-maintainer and anti-cheat review packets for the 11 Gemma-advantage rows that stayed wrong after selective replay, so row-level validity can now govern future training eligibility.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9983 Gemma Advantage Row Review Packets",
                "",
                f"Passed: `{summary['passed']}`",
                f"Review rows: `{built['metrics']['review_rows']}`",
                f"Python rows: `{built['metrics']['python_rows']}`",
                f"C/C++ rows: `{built['metrics']['c_cpp_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "review_rows": built["metrics"]["review_rows"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
