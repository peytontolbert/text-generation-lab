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
STAGE = 9940
NAME = "stage9940_weighted_winner_claim_readiness_matrix"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "weighted_winner_claim_readiness_matrix.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEIGHTED_WINNER_CLAIM_READINESS_MATRIX_STAGE9940.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FRONTIER = ROOT / "runs/local/artifacts/stage9922_current_weighted_hardened_multilingual_frontier_bridge/current_weighted_hardened_multilingual_frontier_bridge.json"
COMPARISON = ROOT / "runs/local/artifacts/stage9919_hardened_weighted_edit_localization_gemma_comparison/hardened_weighted_edit_localization_gemma_comparison.json"
SHORTCUT = ROOT / "runs/local/artifacts/stage9920_hardened_weighted_edit_localization_shortcut_audit/hardened_weighted_edit_localization_shortcut_audit.json"
GLOBAL_EVAL_HACK = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage9934_active_weighted_winner_signoff_workbook/active_weighted_winner_signoff_workbook.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def _cell_packet(lang: str, name: str) -> Path:
    return PACKETS / f"standalone_100m_weights__{lang}__edit_localization" / name


def _subskill_completion(rubric: dict[str, Any]) -> bool:
    values = rubric.get("subskills")
    return isinstance(values, dict) and any(value is not None for value in values.values())


def _challenge_family_map(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("challenge_family") or ""): row
        for row in (card.get("challenge_families") or [])
        if isinstance(row, dict)
    }


def build_matrix() -> dict[str, Any]:
    frontier = load_json(FRONTIER)
    comparison = load_json(COMPARISON)
    shortcut = load_json(SHORTCUT)
    global_eval_hack = load_json(GLOBAL_EVAL_HACK)
    workbook = load_json(WORKBOOK)
    failures: list[str] = []

    frontier_rows = {
        str(row.get("language_family") or ""): row
        for row in (frontier.get("records") or [])
        if isinstance(row, dict)
    }
    shortcut_rows = [row for row in (shortcut.get("records") or []) if isinstance(row, dict)]
    workbook_rows = [row for row in (workbook.get("rows") or []) if isinstance(row, dict)]
    global_challenge = global_eval_hack.get("challenge_matrix") if isinstance(global_eval_hack.get("challenge_matrix"), dict) else {}
    global_eval_hack_passed = bool(global_eval_hack.get("passed")) and bool(global_challenge.get("passed"))
    prompt_label_exposure_buckets = int(shortcut.get("metrics", {}).get("buckets_with_prompt_label_vocab_exposed", 0))
    unique_permutation_maps = int(shortcut.get("metrics", {}).get("unique_permutation_maps", 0))

    matrix_rows: list[dict[str, Any]] = []
    for lang in LANGS:
        frontier_row = frontier_rows.get(lang)
        rubric = load_json(_cell_packet(lang, "expert_maintainer_rubric_review.json"))
        anti_cheat = load_json(_cell_packet(lang, "anti_cheat_review_card.json"))
        if not isinstance(frontier_row, dict):
            failures.append(f"missing_frontier_row:{lang}")
            continue

        lang_shortcut_rows = [row for row in shortcut_rows if str(row.get("language_family") or "") == lang]
        prompt_hidden = all(
            int((row.get("metrics") or {}).get("prompt_rows_with_valid_label_line", 0)) == 0
            for row in lang_shortcut_rows
        ) and bool(lang_shortcut_rows)
        workbook_lang_rows = [row for row in workbook_rows if str(row.get("language_family") or "") == lang]
        challenge_map = _challenge_family_map(anti_cheat)
        metadata_shortcuts = challenge_map.get("metadata_and_graph_shortcuts") or {}

        rubric_signed = bool(rubric.get("status") == "completed" or rubric.get("passed") is True or _subskill_completion(rubric))
        anti_cheat_signed = bool(anti_cheat.get("status") == "completed" or anti_cheat.get("passed") is True)
        metadata_shortcut_attachment_complete = metadata_shortcuts.get("recommended_pass") is not None
        narrow_machine_support = (
            str(frontier_row.get("strict_verdict")) == "100m_better"
            and prompt_hidden
            and global_eval_hack_passed
        )
        narrow_claim_fully_signed = narrow_machine_support and rubric_signed and anti_cheat_signed and metadata_shortcut_attachment_complete
        same_surface_strict = float(frontier_row.get("strict_exact_100m") or 0.0)
        confidence_tier = (
            "higher" if same_surface_strict >= 0.75
            else "moderate" if same_surface_strict >= 0.5
            else "fragile"
        )

        matrix_rows.append({
            "language_family": lang,
            "same_surface_strict_exact_100m": frontier_row.get("strict_exact_100m"),
            "same_surface_strict_exact_gemma12b": frontier_row.get("strict_exact_gemma"),
            "same_surface_verdict": frontier_row.get("strict_verdict"),
            "claim_scope": frontier_row.get("claim_scope"),
            "expert_review_status": rubric.get("status"),
            "anti_cheat_review_status": anti_cheat.get("status"),
            "pending_signoff_tasks": len(workbook_lang_rows),
            "prompt_label_exposure_hardened": prompt_hidden,
            "global_eval_hacking_gate_passed": global_eval_hack_passed,
            "local_metadata_graph_shortcut_evidence_attached": metadata_shortcut_attachment_complete,
            "local_metadata_graph_shortcut_reviewer_confidence": metadata_shortcuts.get("recommendation_confidence"),
            "local_metadata_graph_shortcut_notes": metadata_shortcuts.get("recommendation_notes"),
            "narrow_machine_supported_claim": narrow_machine_support,
            "narrow_claim_fully_signed": narrow_claim_fully_signed,
            "broader_v27_claim_ready": False,
            "same_surface_confidence_tier": confidence_tier,
            "remaining_claim_gaps": [
                *([] if rubric_signed else ["expert_maintainer_human_signoff_missing"]),
                *([] if anti_cheat_signed else ["anti_cheat_human_signoff_missing"]),
                *([] if metadata_shortcut_attachment_complete else ["local_metadata_graph_shortcut_attachment_missing"]),
                *([] if prompt_hidden else ["prompt_label_hardening_not_verified"]),
                *([] if global_eval_hack_passed else ["global_eval_hacking_gate_not_verified"]),
                "broader_v27_claim_not_supported_by_this_narrow_surface",
            ],
            "evidence_paths": {
                "frontier_bridge": display(FRONTIER),
                "same_surface_comparison": display(COMPARISON),
                "same_surface_shortcut_audit": display(SHORTCUT),
                "global_eval_hacking_audit": display(GLOBAL_EVAL_HACK),
                "expert_review_packet": display(_cell_packet(lang, "expert_maintainer_rubric_review.json")),
                "anti_cheat_packet": display(_cell_packet(lang, "anti_cheat_review_card.json")),
            },
        })

    weakest = min(matrix_rows, key=lambda row: float(row.get("same_surface_strict_exact_100m") or 0.0), default=None)
    metrics = {
        "languages_required": len(LANGS),
        "languages_with_narrow_machine_supported_claim": sum(1 for row in matrix_rows if row["narrow_machine_supported_claim"]),
        "languages_with_full_human_signoff": sum(1 for row in matrix_rows if row["narrow_claim_fully_signed"]),
        "languages_missing_local_metadata_graph_shortcut_attachment": sum(
            1 for row in matrix_rows if not row["local_metadata_graph_shortcut_evidence_attached"]
        ),
        "languages_broader_v27_claim_ready": sum(1 for row in matrix_rows if row["broader_v27_claim_ready"]),
        "prompt_label_exposure_buckets": prompt_label_exposure_buckets,
        "unique_permutation_maps": unique_permutation_maps,
        "weakest_language_family": weakest.get("language_family") if isinstance(weakest, dict) else None,
        "weakest_strict_exact_100m": weakest.get("same_surface_strict_exact_100m") if isinstance(weakest, dict) else None,
    }

    if metrics["languages_required"] != 4:
        failures.append("languages_required_not_4")
    if metrics["languages_with_narrow_machine_supported_claim"] != 4:
        failures.append("languages_with_narrow_machine_supported_claim_not_4")
    if metrics["languages_with_full_human_signoff"] != 0:
        failures.append("languages_with_full_human_signoff_not_0")
    if metrics["languages_missing_local_metadata_graph_shortcut_attachment"] != 4:
        failures.append("languages_missing_local_metadata_graph_shortcut_attachment_not_4")
    if metrics["languages_broader_v27_claim_ready"] != 0:
        failures.append("languages_broader_v27_claim_ready_not_0")
    if metrics["prompt_label_exposure_buckets"] != 0:
        failures.append("prompt_label_exposure_buckets_not_0")
    if metrics["unique_permutation_maps"] != 4:
        failures.append("unique_permutation_maps_not_4")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "language_rows": matrix_rows,
        "claim_rules": {
            "narrow_same_surface_claim": "requires same-surface 100m_better verdict, prompt-label hardening, global eval-hacking gate coverage, and human signoff on rubric plus anti-cheat card",
            "broader_v27_claim": "requires valid wins plus signed expert review, signed anti-cheat review, and evidence beyond this narrow edit-localization surface",
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_matrix()
    MATRIX.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Complete the 8 remaining human review tasks and attach local metadata/graph-shortcut evidence on the weighted hardened "
        "winner cells before claiming a fully signed narrow multilingual win; broader v2.7 claims still need valid non-localization surfaces and real harness outputs."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"matrix": display(MATRIX), "doc": display(DOC)},
        "decision": (
            "Materialized a weighted winner claim-readiness matrix that separates real same-surface machine wins from the remaining "
            "expert-review and anti-cheat gaps needed for a defensible multilingual claim."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9940 Weighted Winner Claim Readiness Matrix",
        "",
        f"Passed: `{summary['passed']}`",
        f"Languages with narrow machine-supported claim: `{built['metrics']['languages_with_narrow_machine_supported_claim']}`",
        f"Languages with full human signoff: `{built['metrics']['languages_with_full_human_signoff']}`",
        f"Languages missing local metadata/graph shortcut attachment: `{built['metrics']['languages_missing_local_metadata_graph_shortcut_attachment']}`",
        f"Weakest language family: `{built['metrics']['weakest_language_family']}`",
        "",
        summary["decision"],
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
    }, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
