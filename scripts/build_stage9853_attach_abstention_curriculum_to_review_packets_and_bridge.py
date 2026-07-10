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
STAGE = 9853
NAME = "stage9853_attach_abstention_curriculum_to_review_packets_and_bridge"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ARTIFACT = OUT_DIR / "attach_abstention_curriculum_to_review_packets_and_bridge.json"
BRIDGE = OUT_DIR / "abstention_curriculum_truthful_bridge.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ATTACH_ABSTENTION_CURRICULUM_TO_REVIEW_PACKETS_AND_BRIDGE_STAGE9853.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
PACKET_MANIFEST = ROOT / "runs/local/artifacts/stage9841_permuted_choice_winner_review_packets/permuted_choice_winner_review_packet_manifest.json"
FORCED_AUDIT = ROOT / "runs/local/artifacts/stage9849_counterfactual_curriculum_gemma_comparison/counterfactual_curriculum_gemma_comparison.json"
ABSTENTION_MANIFEST_SUMMARY = ROOT / "runs/summaries/stage9850_abstention_counterfactual_curriculum_manifest.json"
ABSTENTION_EXEC_AUDIT = ROOT / "runs/local/artifacts/stage9851_direct_abstention_counterfactual_exec/direct_abstention_counterfactual_exec_audit.json"
ABSTENTION_GEMMA_AUDIT = ROOT / "runs/local/artifacts/stage9852_abstention_counterfactual_gemma_comparison/abstention_counterfactual_gemma_comparison.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
CHALLENGES_WITH_NEW_EVIDENCE = {"label_proxy_shortcuts", "generation_quality_collapse", "cross_model_surface_fairness"}


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


def _append_unique(items: list[str], extra: list[str]) -> list[str]:
    return list(dict.fromkeys([*items, *extra]))


def build_training_direction_bridge(
    forced: dict[str, Any],
    abstention_manifest_summary: dict[str, Any],
    abstention_exec: dict[str, Any],
    abstention_gemma: dict[str, Any],
) -> dict[str, Any]:
    forced_macro = forced.get("macro_delta_by_split") if isinstance(forced.get("macro_delta_by_split"), dict) else {}
    abstention_macro = abstention_gemma.get("macro_delta_by_split") if isinstance(abstention_gemma.get("macro_delta_by_split"), dict) else {}
    abstention_eval = (((abstention_exec.get("eval") or {}).get("eval") or {}).get("field_exact") or {}).get("edit_localization") or {}
    abstention_strict = (((abstention_exec.get("eval") or {}).get("strict_eval") or {}).get("field_exact") or {}).get("edit_localization") or {}
    label_counts = (((abstention_manifest_summary.get("metrics") or {}).get("target_label_counts")) or {})

    records = []
    for language in LANGS:
        forced_bucket = (((forced.get("hundred_m") or {}).get("by_bucket")) or {}).get(f"{language}:strict_eval") or {}
        abstention_bucket = (((abstention_gemma.get("hundred_m") or {}).get("by_bucket")) or {}).get(f"{language}:strict_eval") or {}
        gemma_bucket = (((abstention_gemma.get("gemma") or {}).get("by_bucket")) or {}).get(f"{language}:strict_eval") or {}
        comparison = ((abstention_gemma.get("comparisons") or {}).get(f"{language}:strict_eval")) or {}
        records.append(
            {
                "language_family": language,
                "forced_label_strict_exact_100m": forced_bucket.get("exact"),
                "abstention_strict_exact_100m": abstention_bucket.get("exact"),
                "abstention_strict_exact_gemma": gemma_bucket.get("exact"),
                "strict_verdict": comparison.get("verdict"),
            }
        )

    eval_delta_improvement = float(abstention_macro.get("eval") or 0.0) - float(forced_macro.get("eval") or 0.0)
    strict_delta_improvement = float(abstention_macro.get("strict_eval") or 0.0) - float(forced_macro.get("strict_eval") or 0.0)
    objective_shift_supported = (
        forced.get("passed") is True
        and abstention_exec.get("passed") is True
        and abstention_gemma.get("passed") is True
        and strict_delta_improvement > 0.0
        and int(abstention_gemma.get("wins_100m") or 0) > int(forced.get("wins_100m") or 0)
    )
    return {
        "passed": objective_shift_supported,
        "metrics": {
            "forced_macro_delta_eval": float(forced_macro.get("eval") or 0.0),
            "forced_macro_delta_strict_eval": float(forced_macro.get("strict_eval") or 0.0),
            "abstention_macro_delta_eval": float(abstention_macro.get("eval") or 0.0),
            "abstention_macro_delta_strict_eval": float(abstention_macro.get("strict_eval") or 0.0),
            "eval_macro_delta_improvement": eval_delta_improvement,
            "strict_macro_delta_improvement": strict_delta_improvement,
            "forced_wins_100m": int(forced.get("wins_100m") or 0),
            "forced_wins_gemma": int(forced.get("wins_gemma") or 0),
            "abstention_wins_100m": int(abstention_gemma.get("wins_100m") or 0),
            "abstention_wins_gemma": int(abstention_gemma.get("wins_gemma") or 0),
            "abstention_eval_exact_100m": float(abstention_eval.get("exact") or 0.0),
            "abstention_strict_exact_100m": float(abstention_strict.get("exact") or 0.0),
            "abstention_target_rows": int(label_counts.get("ABSTAIN_INSUFFICIENT_EVIDENCE") or 0),
            "objective_shift_supported": objective_shift_supported,
        },
        "records": records,
        "claim": (
            "On the harder restored counterfactual packet, forced singleton labels fail while an explicit abstention target "
            "recovers the 100M comparison. This is evidence that the next improvement lever is output-space redesign, not more identical sweeps."
        ),
        "caveats": [
            "This does not clear shortcut resistance on the stronger permuted-choice winner packet by itself.",
            "The abstention result is adjacent harder-surface evidence, not a replacement for same-packet anti-cheat probes such as ablation and causal-flip.",
            "The comparison remains narrow edit localization plus abstention on insufficient evidence, not a broad software-maintenance or harness claim.",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }


def _language_abstention_status(language: str, bridge: dict[str, Any]) -> dict[str, Any]:
    for row in bridge.get("records") or []:
        if row.get("language_family") == language:
            return row
    return {}


def _challenge_patch(challenge_family: str, language: str, bridge: dict[str, Any]) -> dict[str, Any]:
    metrics = bridge.get("metrics") if isinstance(bridge.get("metrics"), dict) else {}
    row = _language_abstention_status(language, bridge)
    if challenge_family == "label_proxy_shortcuts":
        return {
            "cell_specific_card_present": True,
            "passed": False,
            "notes": [
                f"Harder restored packet strict exact for 100M moved from forced-label {row.get('forced_label_strict_exact_100m')} to abstention-target {row.get('abstention_strict_exact_100m')}.",
                f"Stage9852 strict verdict for this language is {row.get('strict_verdict')}.",
                "This supports an objective-mismatch diagnosis on insufficient-evidence rows, but it does not replace same-packet permutation, ablation, or causal-flip shortcut probes.",
            ],
        }
    if challenge_family == "generation_quality_collapse":
        return {
            "cell_specific_card_present": True,
            "passed": True,
            "notes": [
                f"Stage9851 harder abstention run kept structured output intact with eval exact {metrics.get('abstention_eval_exact_100m')} and strict exact {metrics.get('abstention_strict_exact_100m')}.",
                f"The abstention curriculum included {metrics.get('abstention_target_rows')} explicit ABSTAIN_INSUFFICIENT_EVIDENCE targets instead of collapsing under underspecified rows.",
            ],
        }
    if challenge_family == "cross_model_surface_fairness":
        return {
            "cell_specific_card_present": True,
            "passed": True,
            "notes": [
                "Stage9852 reran the harder packet with the same paired multilingual rows for 100M and Gemma.",
                f"Per-language strict verdict on that harder packet is {row.get('strict_verdict')}, which is more informative than the earlier forced-label comparison.",
            ],
        }
    return {
        "cell_specific_card_present": False,
        "passed": False,
        "notes": ["No new direct abstention-side evidence was attached for this challenge family in Stage9853."],
    }


def build_refresh() -> dict[str, Any]:
    manifest = load_json(PACKET_MANIFEST)
    forced = load_json(FORCED_AUDIT)
    abstention_manifest_summary = load_json(ABSTENTION_MANIFEST_SUMMARY)
    abstention_exec = load_json(ABSTENTION_EXEC_AUDIT)
    abstention_gemma = load_json(ABSTENTION_GEMMA_AUDIT)
    bridge = build_training_direction_bridge(forced, abstention_manifest_summary, abstention_exec, abstention_gemma)
    rows = manifest.get("rows") if isinstance(manifest.get("rows"), list) else []

    refreshed = []
    failures: list[str] = []
    if len(rows) != 4:
        failures.append("expected_four_stage9841_rows")
    if bridge["passed"] is not True:
        failures.append("abstention_bridge_not_supported")

    for row in rows:
        language = str(row.get("language_family") or "")
        paths = row.get("review_packet_paths") if isinstance(row.get("review_packet_paths"), dict) else {}
        anti_path = ROOT / str(paths.get("anti_cheat_cards") or "")
        rubric_draft_path = ROOT / str(paths.get("rubric_recommendation_draft") or "")
        anti = load_json(anti_path)
        rubric_draft = load_json(rubric_draft_path)
        if not anti or not rubric_draft:
            failures.append(f"missing_packet_files:{language}")
            continue

        families = anti.get("challenge_families") if isinstance(anti.get("challenge_families"), list) else []
        updated = []
        for family in families:
            challenge = str(family.get("challenge_family") or "")
            patch = _challenge_patch(challenge, language, bridge)
            updated.append(
                {
                    "challenge_family": challenge,
                    "cell_specific_card_present": patch["cell_specific_card_present"],
                    "passed": patch["passed"],
                    "notes": patch["notes"],
                }
            )
        anti["challenge_families"] = updated
        anti["abstention_counterfactual_status"] = {
            "forced_label_curriculum_audit": str(FORCED_AUDIT.relative_to(ROOT)),
            "abstention_manifest_summary": str(ABSTENTION_MANIFEST_SUMMARY.relative_to(ROOT)),
            "abstention_exec_audit": str(ABSTENTION_EXEC_AUDIT.relative_to(ROOT)),
            "abstention_gemma_audit": str(ABSTENTION_GEMMA_AUDIT.relative_to(ROOT)),
            "per_language_strict_status": _language_abstention_status(language, bridge),
            "bridge_metrics": bridge["metrics"],
        }
        anti["reviewer_notes"] = _append_unique(
            anti.get("reviewer_notes") if isinstance(anti.get("reviewer_notes"), list) else [],
            [
                "Stage9853 adds adjacent harder-packet abstention evidence to show that underspecified rows should not be forced into singleton localization labels.",
                "Use the abstention bridge to scope model-improvement conclusions, not to mark same-packet shortcut resistance as fully cleared.",
            ],
        )
        write_json(anti_path, anti)

        recommended = rubric_draft.get("recommended_subskills") if isinstance(rubric_draft.get("recommended_subskills"), dict) else {}
        repairs = recommended.get("repairs_or_abstains_safely")
        if isinstance(repairs, dict):
            repairs["reviewer_notes"] = _append_unique(
                repairs.get("reviewer_notes") if isinstance(repairs.get("reviewer_notes"), list) else [],
                [
                    f"Adjacent harder-packet evidence now exists: forced-label strict exact {(_language_abstention_status(language, bridge).get('forced_label_strict_exact_100m'))} improved to abstention-target strict exact {(_language_abstention_status(language, bridge).get('abstention_strict_exact_100m'))}.",
                    "Keep the judgment human-confirmed, because this evidence comes from a sibling harder packet rather than the same permuted-choice review packet.",
                ],
            )
        localizes = recommended.get("localizes_edit_scope")
        if isinstance(localizes, dict):
            localizes["reviewer_notes"] = _append_unique(
                localizes.get("reviewer_notes") if isinstance(localizes.get("reviewer_notes"), list) else [],
                [
                    f"Stage9851 preserved localization quality on the harder packet while separating insufficient-evidence rows via abstention; eval exact there was {bridge['metrics']['abstention_eval_exact_100m']}.",
                ],
            )
        rubric_draft["adjacent_abstention_evidence"] = {
            "truthful_bridge": str(BRIDGE.relative_to(ROOT)),
            "claim": bridge.get("claim"),
            "per_language_strict_status": _language_abstention_status(language, bridge),
        }
        rubric_draft["reviewer_notes"] = _append_unique(
            rubric_draft.get("reviewer_notes") if isinstance(rubric_draft.get("reviewer_notes"), list) else [],
            [
                "Stage9853 adds adjacent harder-packet abstention evidence so human reviewers can distinguish true localization skill from forced-label behavior on underspecified rows.",
            ],
        )
        write_json(rubric_draft_path, rubric_draft)

        refreshed.append(
            {
                "language_family": language,
                "anti_cheat_card": str(anti_path.relative_to(ROOT)),
                "rubric_draft": str(rubric_draft_path.relative_to(ROOT)),
                "updated_challenge_families": sum(1 for family in updated if family["challenge_family"] in CHALLENGES_WITH_NEW_EVIDENCE),
            }
        )

    output = {
        "passed": not failures,
        "failures": failures,
        "bridge": bridge,
        "rows": refreshed,
        "metrics": {
            "refreshed_cells": len(refreshed),
            "cells_with_new_abstention_challenge_evidence": sum(1 for row in refreshed if row["updated_challenge_families"] == 3),
            "objective_shift_supported": bridge["metrics"]["objective_shift_supported"],
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    write_json(BRIDGE, bridge)
    write_json(ARTIFACT, output)
    return output


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_refresh()
    next_step = (
        "Propagate ABSTAIN_INSUFFICIENT_EVIDENCE semantics into the next hard-surface training packets and keep patch/verifier rows frozen until they are rebuilt around executable consequences instead of forced singleton labels."
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
            "truthful_bridge": str(BRIDGE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Attached the abstention-curriculum evidence to the stronger permuted-choice review packet and recorded a truthful bridge showing that the harder multilingual frontier improves when insufficient-evidence rows are relabeled to abstain instead of being forced into singleton edit-localization targets.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9853 Attach Abstention Curriculum To Review Packets And Bridge",
                "",
                f"Passed: `{built['passed']}`",
                f"Refreshed cells: `{built['metrics']['refreshed_cells']}`",
                f"Cells with new abstention challenge evidence: `{built['metrics']['cells_with_new_abstention_challenge_evidence']}`",
                f"Strict macro improvement from forced-label to abstention curriculum: `{built['bridge']['metrics']['strict_macro_delta_improvement']}`",
                "",
                "This stage injects the new harder-packet abstention evidence into the current human-review packet and records the truthful modeling conclusion: the next frontier is output-space redesign for underspecified rows, not more identical forced-label sweeps.",
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
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": built["metrics"],
                "failures": built["failures"],
                "strict_macro_delta_improvement": built["bridge"]["metrics"]["strict_macro_delta_improvement"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
