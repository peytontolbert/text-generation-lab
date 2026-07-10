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
STAGE = 10016
NAME = "stage10016_quarantined_blended_weak_language_same_manifest_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "quarantined_blended_weak_language_same_manifest_review_packets.jsonl"
MANIFEST = OUT_DIR / "quarantined_blended_weak_language_same_manifest_review_manifest.json"
AUDIT = OUT_DIR / "quarantined_blended_weak_language_same_manifest_review_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "QUARANTINED_BLENDED_WEAK_LANGUAGE_SAME_MANIFEST_REVIEW_PACKETS_STAGE10016.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUEST = ROOT / "runs/local/artifacts/stage10013_quarantined_blended_weak_language_target100m_execution_request/surface_requests/edit_localization.json"
HANDOFF = ROOT / "runs/local/artifacts/stage10014_quarantined_blended_weak_language_same_manifest_handoff_bundle/quarantined_blended_weak_language_same_manifest_handoff_bundle.json"
RUBRIC_SUBSKILLS_PATH = ROOT / "scripts/build_stage9719_multilingual_comparison_evidence_bundle_contract.py"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
APPLICABLE_SUBSKILLS = {
    "avoids_hallucinated_symbols",
    "avoids_internal_tokens",
    "binds_symbols_correctly",
    "localizes_edit_scope",
    "produces_contentful_final_answer",
    "repairs_or_abstains_safely",
    "retrieves_source_evidence_when_needed",
    "understands_user_intent",
}
CHALLENGE_FAMILIES = [
    "target_and_teacher_leakage",
    "label_proxy_shortcuts",
    "raw_source_or_symbol_leakage",
    "source_lineage_and_gate_integrity",
    "same_manifest_cross_model_fairness",
    "evaluation_replay_scope_discipline",
]


def _load_symbol(module_name: str, path: Path, symbol: str):
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


RUBRIC_SUBSKILLS = _load_symbol(
    "stage10016_stage9719_contract",
    RUBRIC_SUBSKILLS_PATH,
    "RUBRIC_SUBSKILLS",
)


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


def packet_dir(language: str) -> Path:
    return OUT_DIR / "review_packets" / f"quarantined_blended_target100m__{language}__edit_localization"


def packet_paths(language: str) -> dict[str, str]:
    base = packet_dir(language)
    return {
        "packet_dir": display(base),
        "expert_maintainer_rubric_review": display(base / "expert_maintainer_rubric_review.json"),
        "anti_cheat_review_card": display(base / "anti_cheat_review_card.json"),
        "expert_maintainer_recommendation_draft": display(base / "expert_maintainer_recommendation_draft.json"),
        "anti_cheat_recommendation_draft": display(base / "anti_cheat_recommendation_draft.json"),
    }


def compare_rows_only(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if str(row.get("split") or "") in {"eval", "strict_eval"}]
    selected.sort(key=lambda row: str(row.get("row_id") or ""))
    return selected


def language_rows(rows: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("language_family") or row.get("language") or "") == language]


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("split") or "other") for row in rows)
    return {
        "train": counts.get("train", 0),
        "eval": counts.get("eval", 0),
        "strict_eval": counts.get("strict_eval", 0),
    }


def all_gate_status_true(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        gate_status = row.get("gate_status") if isinstance(row.get("gate_status"), dict) else {}
        if not gate_status or not all(bool(value) for value in gate_status.values()):
            return False
    return True


def boolean_all(rows: list[dict[str, Any]], path: tuple[str, ...]) -> bool:
    for row in rows:
        current: Any = row
        for key in path:
            if not isinstance(current, dict):
                return False
            current = current.get(key)
        if current is not True:
            return False
    return True


def boolean_none_true(rows: list[dict[str, Any]], path: tuple[str, ...]) -> bool:
    for row in rows:
        current: Any = row
        for key in path:
            if not isinstance(current, dict):
                return False
            current = current.get(key)
        if current is True:
            return False
    return True


def recommendation_subskills(language: str, compare_count: int) -> dict[str, dict[str, Any]]:
    supported_note = (
        f"This quarantined same-manifest weak-language packet exposes evidence-grounded opaque edit-localization choices for `{language}` "
        f"across `{compare_count}` compare rows, so this rubric line becomes scoreable once real Stage10013 and Stage10015 outputs exist."
    )
    out: dict[str, dict[str, Any]] = {}
    for name in RUBRIC_SUBSKILLS:
        if name in APPLICABLE_SUBSKILLS:
            out[name] = {
                "surface_supports_scoring_after_execution": True,
                "recommended_judgment_now": None,
                "confidence": "requires_real_outputs",
                "reviewer_notes": [supported_note],
            }
        else:
            out[name] = {
                "surface_supports_scoring_after_execution": False,
                "recommended_judgment_now": None,
                "confidence": "out_of_scope",
                "reviewer_notes": ["This same-manifest packet is edit localization only and should not be used to score this maintainer rubric line."],
            }
    return out


def challenge_rows(language: str, metrics: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "challenge_family": "target_and_teacher_leakage",
            "recommended_pass": bool(metrics["no_target_label_in_id"] and metrics["no_target_literals_in_prompt_surface"]),
            "confidence": "high",
            "reviewer_notes": [
                "Row ids do not embed the target label.",
                "The row anti-cheat contract records that target-label literals are not exposed in the prompt surface.",
            ],
        },
        {
            "challenge_family": "label_proxy_shortcuts",
            "recommended_pass": bool(metrics["opaque_choice_surface"] and metrics["unique_permutation_maps"] >= 4),
            "confidence": "high",
            "reviewer_notes": [
                f"Unique row-local permutation maps for `{language}`: `{metrics['unique_permutation_maps']}`.",
                "The packet stays inside an opaque A-to-E choice protocol rather than a fixed visible label list.",
            ],
        },
        {
            "challenge_family": "raw_source_or_symbol_leakage",
            "recommended_pass": bool(metrics["no_raw_source_included"] and metrics["no_raw_symbol_names_in_model_input"]),
            "confidence": "high",
            "reviewer_notes": [
                "The row anti-cheat contract marks raw source and raw symbol names as absent from model input.",
            ],
        },
        {
            "challenge_family": "source_lineage_and_gate_integrity",
            "recommended_pass": bool(metrics["all_source_backed"] and metrics["all_gate_status_true"]),
            "confidence": "high",
            "reviewer_notes": [
                "Every row remains source-backed and carries a fully true gate-status bundle before use in this packet.",
            ],
        },
        {
            "challenge_family": "same_manifest_cross_model_fairness",
            "recommended_pass": True,
            "confidence": "medium",
            "reviewer_notes": [
                "Stage10014 binds the future 100M and Gemma runs to the same manifest and same compare-row ids.",
                "Final fairness still requires the real Stage10013 and Stage10015 outputs to land on that exact manifest.",
            ],
        },
        {
            "challenge_family": "evaluation_replay_scope_discipline",
            "recommended_pass": bool(metrics["compare_rows"] > 0 and metrics["eval_replay_rows"] > 0),
            "confidence": "medium",
            "reviewer_notes": [
                f"Compare rows for `{language}`: `{metrics['compare_rows']}`; eval-replay tagged rows: `{metrics['eval_replay_rows']}`.",
                "The packet distinguishes execution compare rows from train-only replay and keeps harder counterfactual siblings outside the claim surface.",
            ],
        },
    ]


def build_packets() -> dict[str, Any]:
    request = load_json(REQUEST)
    handoff = load_json(HANDOFF)
    failures: list[str] = []

    manifest_path = ROOT / str(request.get("manifest") or "")
    rows = load_jsonl(manifest_path) if manifest_path.exists() else []
    compare_rows = compare_rows_only(rows)
    handoff_bundle = handoff.get("handoff_bundle") if isinstance(handoff.get("handoff_bundle"), dict) else {}
    row_contract = handoff_bundle.get("row_contract") if isinstance(handoff_bundle.get("row_contract"), dict) else {}

    if request.get("surface") != "edit_localization":
        failures.append("stage10013_request_not_edit_localization")
    if handoff.get("passed") is not True:
        failures.append("stage10014_not_passed")
    if not rows:
        failures.append("missing_manifest_rows")
    if len(compare_rows) != int(row_contract.get("same_manifest_compare_rows") or -1):
        failures.append("same_manifest_compare_rows_mismatch")

    review_rows: list[dict[str, Any]] = []
    language_cards: list[dict[str, Any]] = []
    for language in LANGS:
        lang_rows = language_rows(rows, language)
        lang_compare = compare_rows_only(lang_rows)
        perm_maps = {json.dumps(row.get("choice_permutation_map") or {}, sort_keys=True) for row in lang_rows}
        semantic_keys = {str(row.get("semantic_key") or "") for row in lang_compare}
        counterfactual_groups = {str(row.get("counterfactual_group_id") or "") for row in lang_rows}
        metrics = {
            "rows": len(lang_rows),
            "compare_rows": len(lang_compare),
            "split_counts": split_counts(lang_rows),
            "unique_permutation_maps": len(perm_maps),
            "unique_compare_semantic_keys": len([value for value in semantic_keys if value]),
            "unique_counterfactual_groups": len([value for value in counterfactual_groups if value]),
            "opaque_choice_surface": boolean_all(lang_rows, ("anti_cheat", "opaque_choice_surface")),
            "no_target_label_in_id": boolean_none_true(lang_rows, ("anti_cheat", "target_label_in_id")),
            "no_target_literals_in_prompt_surface": boolean_none_true(lang_rows, ("anti_cheat", "target_label_literals_in_prompt_surface")),
            "no_target_path_in_model_input": boolean_none_true(lang_rows, ("anti_cheat", "target_path_in_model_input")),
            "no_raw_source_included": boolean_none_true(lang_rows, ("anti_cheat", "raw_source_included")),
            "no_raw_symbol_names_in_model_input": boolean_none_true(lang_rows, ("anti_cheat", "raw_symbol_names_in_model_input")),
            "all_source_backed": all(bool(row.get("source_backed")) for row in lang_rows),
            "all_source_row_id_hidden": all(not bool(((row.get("source_row_ref") or {}).get("source_row_id_in_model_input"))) for row in lang_rows),
            "all_gate_status_true": all_gate_status_true(lang_rows),
            "eval_replay_rows": sum(1 for row in lang_compare if "eval_replay" in str(row.get("counterfactual_role") or "")),
        }
        paths = packet_paths(language)
        rubric_stub = {
            "cell_key": f"quarantined_blended_target100m::{language}::edit_localization::same_manifest_review",
            "language_family": language,
            "status": "pending_real_outputs_and_human_review",
            "rubric_version": "expert_maintainer_v1",
            "passed": False,
            "requires_real_stage10013_outputs": True,
            "requires_real_stage10015_outputs": True,
            "required_human_action": "Score only the in-scope localization/evidence-grounding rubric lines after reviewing real same-manifest 100M and Gemma outputs.",
            "in_scope_subskills": sorted(APPLICABLE_SUBSKILLS),
            "out_of_scope_subskills": sorted(set(RUBRIC_SUBSKILLS) - APPLICABLE_SUBSKILLS),
            "subskills": {name: None for name in RUBRIC_SUBSKILLS},
            "machine_scope_recommendations": recommendation_subskills(language, len(lang_compare)),
            "supporting_evidence_paths": {
                "same_manifest_request": display(REQUEST),
                "same_manifest_handoff_bundle": display(HANDOFF),
                "future_stage10013_output_dir": str((handoff.get("handoff_bundle") or handoff).get("hundred_m_execution", {}).get("future_output_dir") or ""),
                "future_stage10015_output_stub": str((handoff.get("handoff_bundle") or handoff).get("gemma_execution", {}).get("future_output_stub") or ""),
            },
            "surface_metrics": metrics,
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_stub = {
            "cell_key": rubric_stub["cell_key"],
            "language_family": language,
            "status": "pending_real_outputs_and_human_review",
            "passed": False,
            "must_pass_global_stage9717_gate": True,
            "same_manifest_compare_rows": len(lang_compare),
            "challenge_families": challenge_rows(language, metrics),
            "machine_supporting_metrics": metrics,
            "required_human_action": "Confirm the machine-supported anti-cheat signals on the exact same-manifest packet, then recheck them against real Stage10013 and Stage10015 outputs.",
            "supporting_evidence_paths": {
                "same_manifest_request": display(REQUEST),
                "same_manifest_handoff_bundle": display(HANDOFF),
            },
            "authority": dict(AUTHORITY_CLOSED),
        }
        rubric_draft = {
            "cell_key": rubric_stub["cell_key"],
            "language_family": language,
            "review_scope_summary": (
                "This packet is appropriate for the 8 localization/evidence-grounding maintainer rubric lines only. "
                "It should not be used to score patch selection, imports, test creation, or verifier-command lines."
            ),
            "compare_rows": len(lang_compare),
            "in_scope_subskills": sorted(APPLICABLE_SUBSKILLS),
            "out_of_scope_subskills": sorted(set(RUBRIC_SUBSKILLS) - APPLICABLE_SUBSKILLS),
            "pending_requirements": [
                "real_stage10013_100m_outputs",
                "real_stage10015_gemma_outputs",
                "human_rubric_signoff",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_draft = {
            "cell_key": rubric_stub["cell_key"],
            "language_family": language,
            "summary": (
                "The same-manifest weak-language packet preserves opaque choices, hidden source ids, gate-status lineage, "
                "and row-local permutation diversity before execution. Final anti-cheat signoff still depends on checking "
                "the real Stage10013 and Stage10015 outputs on this exact manifest."
            ),
            "recommended_pass_families": [
                row["challenge_family"]
                for row in anti_stub["challenge_families"]
                if row.get("recommended_pass") is True
            ],
            "pending_requirements": [
                "real_stage10013_100m_outputs",
                "real_stage10015_gemma_outputs",
                "human_anti_cheat_signoff",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }

        write_json(ROOT / paths["expert_maintainer_rubric_review"], rubric_stub)
        write_json(ROOT / paths["anti_cheat_review_card"], anti_stub)
        write_json(ROOT / paths["expert_maintainer_recommendation_draft"], rubric_draft)
        write_json(ROOT / paths["anti_cheat_recommendation_draft"], anti_draft)

        review_rows.append({
            "cell_key": rubric_stub["cell_key"],
            "language_family": language,
            "compare_rows": len(lang_compare),
            "packet_paths": paths,
            "pending_requirements": [
                "real_stage10013_100m_outputs",
                "real_stage10015_gemma_outputs",
                "human_rubric_signoff",
                "human_anti_cheat_signoff",
            ],
        })
        language_cards.append({
            "language_family": language,
            **metrics,
            "in_scope_subskills": sorted(APPLICABLE_SUBSKILLS),
            "out_of_scope_subskills": sorted(set(RUBRIC_SUBSKILLS) - APPLICABLE_SUBSKILLS),
        })

        if metrics["rows"] <= 0:
            failures.append(f"missing_rows:{language}")
        if metrics["compare_rows"] <= 0:
            failures.append(f"missing_compare_rows:{language}")
        if metrics["unique_permutation_maps"] < 4:
            failures.append(f"too_few_permutation_maps:{language}:{metrics['unique_permutation_maps']}")
        if metrics["opaque_choice_surface"] is not True:
            failures.append(f"opaque_choice_surface_missing:{language}")
        if metrics["all_gate_status_true"] is not True:
            failures.append(f"gate_status_incomplete:{language}")

    audit = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "languages": len(language_cards),
            "review_packets": len(review_rows),
            "same_manifest_compare_rows": len(compare_rows),
            "languages_with_machine_supported_applicable_scope": sum(
                1 for row in language_cards if set(row["in_scope_subskills"]) == APPLICABLE_SUBSKILLS
            ),
            "languages_with_clean_anti_cheat_contract": sum(
                1
                for row in language_cards
                if row["opaque_choice_surface"]
                and row["no_target_label_in_id"]
                and row["no_target_literals_in_prompt_surface"]
                and row["no_raw_source_included"]
                and row["no_raw_symbol_names_in_model_input"]
                and row["all_gate_status_true"]
            ),
            "weakest_language_by_compare_rows": min(language_cards, key=lambda row: row["compare_rows"])["language_family"] if language_cards else None,
        },
        "language_cards": language_cards,
        "authority": dict(AUTHORITY_CLOSED),
    }
    return {
        "passed": audit["passed"],
        "failures": failures,
        "audit": audit,
        "review_rows": review_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packets()
    write_json(AUDIT, built["audit"])
    write_json(MANIFEST, {"rows": built["review_rows"], "authority": dict(AUTHORITY_CLOSED)})
    write_jsonl(PACKETS, built["review_rows"])
    next_step = (
        "Use these quarantined same-manifest weak-language review packets to keep expert-maintainer and anti-cheat review aligned with the exact Stage10013/Stage10015 comparison surface, then attach real outputs there before making any broader multilingual claim."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["audit"]["metrics"], "failures": built["failures"]},
        "artifacts": {
            "audit": display(AUDIT),
            "manifest": display(MANIFEST),
            "packets": display(PACKETS),
            "doc": display(DOC),
        },
        "decision": "Materialized reviewer-facing quarantined same-manifest weak-language packets that tie expert-maintainer scope and anti-cheat checks to the exact Stage10013/Stage10015 comparison surface without pretending the real model outputs already exist.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text("\n".join([
        "# Stage10016 Quarantined Blended Weak-Language Same-Manifest Review Packets",
        "",
        f"Passed: `{summary['passed']}`",
        f"Review packets: `{built['audit']['metrics']['review_packets']}`",
        f"Same-manifest compare rows: `{built['audit']['metrics']['same_manifest_compare_rows']}`",
        f"Languages with machine-supported applicable scope: `{built['audit']['metrics']['languages_with_machine_supported_applicable_scope']}`",
        f"Languages with clean anti-cheat contract: `{built['audit']['metrics']['languages_with_clean_anti_cheat_contract']}`",
        "",
        summary["decision"],
        "",
        "This stage is still pre-execution. It packages what the surface can honestly support and what anti-cheat evidence is already machine-backed, but it does not claim any new 100M-vs-Gemma win.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "metrics": built["audit"]["metrics"],
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
