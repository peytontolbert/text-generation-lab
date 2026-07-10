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
STAGE = 9959
NAME = "stage9959_weighted_winner_review_scope_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "weighted_winner_review_scope_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEIGHTED_WINNER_REVIEW_SCOPE_AUDIT_STAGE9959.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FRONTIER = ROOT / "runs/local/artifacts/stage9922_current_weighted_hardened_multilingual_frontier_bridge/current_weighted_hardened_multilingual_frontier_bridge.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"
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
OUT_OF_SCOPE_MARKERS = (
    "not rewrite execution",
    "not operator choice",
    "not test creation",
    "not a verifier-command surface",
    "does not directly exercise imports",
    "does not directly exercise blocked imports",
    "identifies bounded edit targets rather than applying patches",
)


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


def _packet(lang: str, name: str) -> Path:
    return PACKETS / f"standalone_100m_weights__{lang}__edit_localization" / name


def _confidence_tier(strict_exact: float) -> str:
    if strict_exact >= 0.75:
        return "high"
    if strict_exact >= 0.5:
        return "moderate"
    return "fragile"


def _classify_null_subskill(entry: dict[str, Any]) -> str:
    notes = " ".join(str(note) for note in (entry.get("reviewer_notes") or []))
    if any(marker in notes for marker in OUT_OF_SCOPE_MARKERS):
        return "out_of_scope"
    return "ambiguous_or_requires_human_judgment"


def _frontier_rows() -> dict[str, dict[str, Any]]:
    frontier = load_json(FRONTIER)
    return {
        str(row.get("language_family") or ""): row
        for row in (frontier.get("records") or [])
        if isinstance(row, dict)
    }


def build_audit() -> dict[str, Any]:
    frontier_rows = _frontier_rows()
    failures: list[str] = []
    rows: list[dict[str, Any]] = []

    for lang in LANGS:
        frontier = frontier_rows.get(lang)
        rubric = load_json(_packet(lang, "expert_maintainer_rubric_review.json"))
        anti = load_json(_packet(lang, "anti_cheat_review_card.json"))
        if not isinstance(frontier, dict):
            failures.append(f"missing_frontier_row:{lang}")
            continue
        recommended = rubric.get("recommended_subskills")
        challenges = anti.get("challenge_families")
        if not isinstance(recommended, dict):
            failures.append(f"missing_recommended_subskills:{lang}")
            continue
        if not isinstance(challenges, list):
            failures.append(f"missing_challenge_families:{lang}")
            continue

        applicable_supported: list[str] = []
        applicable_supported_confident: list[str] = []
        out_of_scope: list[str] = []
        ambiguous: list[str] = []
        supported_requires_human_confirmation: list[str] = []

        for name, raw_entry in recommended.items():
            if not isinstance(raw_entry, dict):
                failures.append(f"bad_subskill_entry:{lang}:{name}")
                continue
            recommended_judgment = raw_entry.get("recommended_judgment")
            confidence = str(raw_entry.get("confidence") or "")
            if recommended_judgment is True:
                applicable_supported.append(name)
                if confidence in {"high", "medium"}:
                    applicable_supported_confident.append(name)
                else:
                    supported_requires_human_confirmation.append(name)
            elif recommended_judgment is None:
                category = _classify_null_subskill(raw_entry)
                if category == "out_of_scope":
                    out_of_scope.append(name)
                else:
                    ambiguous.append(name)

        direct_pass = []
        inherited_pass = []
        for raw_row in challenges:
            if not isinstance(raw_row, dict):
                continue
            family = str(raw_row.get("challenge_family") or "")
            if raw_row.get("recommended_pass") is not True:
                continue
            if isinstance(raw_row.get("upstream_global_evidence"), dict):
                inherited_pass.append(family)
            else:
                direct_pass.append(family)

        strict_exact = float(frontier.get("strict_exact_100m") or 0.0)
        row = {
            "language_family": lang,
            "same_surface_strict_exact_100m": strict_exact,
            "same_surface_strict_exact_gemma12b": frontier.get("strict_exact_gemma"),
            "same_surface_verdict": frontier.get("strict_verdict"),
            "same_surface_confidence_tier": _confidence_tier(strict_exact),
            "rubric_total_subskills": len(recommended),
            "rubric_applicable_supported_subskills": sorted(applicable_supported),
            "rubric_applicable_supported_count": len(applicable_supported),
            "rubric_confidently_supported_subskills": sorted(applicable_supported_confident),
            "rubric_confidently_supported_count": len(applicable_supported_confident),
            "rubric_supported_but_human_confirmation_subskills": sorted(supported_requires_human_confirmation),
            "rubric_supported_but_human_confirmation_count": len(supported_requires_human_confirmation),
            "rubric_out_of_scope_subskills": sorted(out_of_scope),
            "rubric_out_of_scope_count": len(out_of_scope),
            "rubric_ambiguous_subskills": sorted(ambiguous),
            "rubric_ambiguous_count": len(ambiguous),
            "rubric_applicable_scope_machine_supported": set(applicable_supported) == APPLICABLE_SUBSKILLS,
            "rubric_applicable_scope_confidently_supported": set(applicable_supported_confident) == APPLICABLE_SUBSKILLS,
            "anti_cheat_direct_pass_families": sorted(direct_pass),
            "anti_cheat_direct_pass_count": len(direct_pass),
            "anti_cheat_inherited_global_gate_families": sorted(inherited_pass),
            "anti_cheat_inherited_global_gate_count": len(inherited_pass),
            "review_scope_recommendation": (
                "Score only the 8 localization/evidence-grounding rubric lines as in-scope for this packet; "
                "mark patch, import, test-creation, and verifier-command lines as not exercised here."
            ),
            "followup_recommendation": (
                "Use the targeted web refresh path before final signoff."
                if lang == "web_js_ts_html"
                else "Human review can focus on confirming the already-supported localization subskills and anti-cheat passes."
            ),
            "evidence_paths": {
                "frontier_bridge": display(FRONTIER),
                "rubric_review": display(_packet(lang, "expert_maintainer_rubric_review.json")),
                "anti_cheat_review": display(_packet(lang, "anti_cheat_review_card.json")),
            },
        }
        rows.append(row)

        if row["rubric_total_subskills"] != 16:
            failures.append(f"rubric_total_subskills_not_16:{lang}")
        if row["rubric_applicable_supported_count"] != 8:
            failures.append(f"rubric_applicable_supported_count_not_8:{lang}")
        if row["rubric_out_of_scope_count"] < 7:
            failures.append(f"rubric_out_of_scope_count_too_low:{lang}")
        if row["anti_cheat_direct_pass_count"] < 5:
            failures.append(f"anti_cheat_direct_pass_count_too_low:{lang}")
        if row["anti_cheat_inherited_global_gate_count"] != 1:
            failures.append(f"anti_cheat_inherited_global_gate_count_not_1:{lang}")

    weakest = min(rows, key=lambda row: float(row.get("same_surface_strict_exact_100m") or 0.0), default=None)
    metrics = {
        "languages_required": len(LANGS),
        "languages_with_machine_supported_applicable_rubric_scope": sum(
            1 for row in rows if row["rubric_applicable_scope_machine_supported"]
        ),
        "languages_with_confident_machine_supported_applicable_rubric_scope": sum(
            1 for row in rows if row["rubric_applicable_scope_confidently_supported"]
        ),
        "languages_with_clean_out_of_scope_partition": sum(
            1 for row in rows if row["rubric_out_of_scope_count"] >= 7 and row["rubric_ambiguous_count"] <= 1
        ),
        "languages_with_direct_plus_inherited_anti_cheat_support": sum(
            1 for row in rows if row["anti_cheat_direct_pass_count"] >= 5 and row["anti_cheat_inherited_global_gate_count"] == 1
        ),
        "weakest_language_family": weakest.get("language_family") if isinstance(weakest, dict) else None,
        "weakest_strict_exact_100m": weakest.get("same_surface_strict_exact_100m") if isinstance(weakest, dict) else None,
        "weakest_language_confidence_tier": weakest.get("same_surface_confidence_tier") if isinstance(weakest, dict) else None,
    }
    if metrics["languages_required"] != 4:
        failures.append("languages_required_not_4")
    if metrics["languages_with_machine_supported_applicable_rubric_scope"] != 4:
        failures.append("languages_with_machine_supported_applicable_rubric_scope_not_4")
    if metrics["languages_with_confident_machine_supported_applicable_rubric_scope"] != 3:
        failures.append("languages_with_confident_machine_supported_applicable_rubric_scope_not_3")
    if metrics["languages_with_clean_out_of_scope_partition"] != 4:
        failures.append("languages_with_clean_out_of_scope_partition_not_4")
    if metrics["languages_with_direct_plus_inherited_anti_cheat_support"] != 4:
        failures.append("languages_with_direct_plus_inherited_anti_cheat_support_not_4")
    if metrics["weakest_language_family"] != "web_js_ts_html":
        failures.append("weakest_language_family_not_web")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "language_rows": rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use this scope audit to score only the 8 in-scope localization rubric lines during human signoff, and route web_js_ts_html through the targeted refresh path before treating its narrow winner as robust."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Materialized a weighted winner review-scope audit that separates the 8 localization-relevant rubric lines from the out-of-scope maintainer lines and quantifies which languages have confident machine support versus fragile support.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9959 Weighted Winner Review Scope Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Languages with machine-supported applicable rubric scope: `{built['metrics']['languages_with_machine_supported_applicable_rubric_scope']}`",
        f"Languages with confidently supported applicable rubric scope: `{built['metrics']['languages_with_confident_machine_supported_applicable_rubric_scope']}`",
        f"Weakest language family: `{built['metrics']['weakest_language_family']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
