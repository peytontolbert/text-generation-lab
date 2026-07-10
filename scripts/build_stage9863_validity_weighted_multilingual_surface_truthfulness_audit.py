#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9863
NAME = "stage9863_validity_weighted_multilingual_surface_truthfulness_audit"
SOURCE_9857 = ROOT / "runs/summaries/stage9857_v27_validity_weighted_multisurface_compiler_refresh.json"
SOURCE_9859 = ROOT / "runs/summaries/stage9859_validity_weighted_structured_tiny_execution_review.json"
SOURCE_9862 = ROOT / "runs/summaries/stage9862_symbol_binding_target_100m_structured_tiny_probe_audit.json"
TINY_DIR = ROOT / "runs/local/artifacts/stage9859_validity_weighted_structured_tiny_execution_review/tiny_structured_manifests"
STAGE9859_TICKET = ROOT / "runs/local/artifacts/stage9859_validity_weighted_structured_tiny_execution_review/validity_weighted_structured_tiny_execution_review_inactive.json"
STAGE9862_EXECUTION = ROOT / "runs/local/artifacts/stage9862_symbol_binding_target_100m_structured_tiny_probe/symbol_binding_probe/execution_result.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "validity_weighted_multilingual_surface_truthfulness_audit.json"
NEXT_CANDIDATE = OUT_DIR / "stage9864_edit_localization_target_100m_structured_tiny_probe_candidate.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VALIDITY_WEIGHTED_MULTILINGUAL_SURFACE_TRUTHFULNESS_AUDIT_STAGE9863.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED_LANGUAGES = ["python", "rust", "c_cpp", "web_js_ts_html"]

SURFACE_SPECS = {
    "symbol_binding": {"mode": "symbol_binding_probe", "loss": "symbol_binding_ce"},
    "edit_localization": {"mode": "edit_localization_probe", "loss": "edit_localization_ce"},
    "patch_operator_selection": {"mode": "patch_operator_probe", "loss": "patch_operator_ce"},
    "verifier_failure_repair_or_abstain": {"mode": "verifier_repair_probe", "loss": "verifier_repair_ce"},
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def infer_language(row: dict[str, Any]) -> str:
    direct = str(row.get("language_family") or row.get("language") or "").strip()
    if direct and direct != "unknown":
        return direct
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        features = node.get("features") if isinstance(node.get("features"), dict) else {}
        lang = str(features.get("language_family") or "").strip()
        if lang and lang != "unknown":
            return lang
    evidence = row.get("evidence_bundle") if isinstance(row.get("evidence_bundle"), dict) else {}
    lang = str(evidence.get("language_family") or "").strip()
    if lang and lang != "unknown":
        return lang
    return direct or "unknown"


def surface_language_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    top = Counter()
    inferred = Counter()
    split_lang = defaultdict(Counter)
    for row in rows:
        top[str(row.get("language_family") or row.get("language") or "unknown")] += 1
        lang = infer_language(row)
        inferred[lang] += 1
        split_lang[str(row.get("split") or "other")][lang] += 1
    missing = [lang for lang in REQUIRED_LANGUAGES if inferred.get(lang, 0) <= 0]
    split_ready = {
        split: all(split_lang.get(split, Counter()).get(lang, 0) > 0 for lang in REQUIRED_LANGUAGES)
        for split in ["train", "eval", "strict_eval"]
    }
    return {
        "rows": len(rows),
        "top_level_language_counts": dict(sorted(top.items())),
        "inferred_language_counts": dict(sorted(inferred.items())),
        "split_language_counts": {split: dict(sorted(counter.items())) for split, counter in sorted(split_lang.items())},
        "missing_required_languages": missing,
        "multilingual_ready": not missing and all(split_ready.values()),
        "split_multilingual_ready": split_ready,
    }


def build_next_command(ticket: dict[str, Any]) -> list[str]:
    cmd = list((ticket.get("surface_commands") or {}).get("edit_localization") or [])
    if not cmd:
        return []
    out_idx = cmd.index("--output-dir") + 1
    run_idx = cmd.index("--run-id") + 1
    cmd[out_idx] = "runs/local/artifacts/stage9864_edit_localization_target_100m_structured_tiny_probe/edit_localization_probe"
    cmd[run_idx] = "stage9864_edit_localization_target_100m_structured_tiny_probe"
    return cmd


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source_9857 = load_json(SOURCE_9857)
    source_9859 = load_json(SOURCE_9859)
    source_9862 = load_json(SOURCE_9862)
    ticket = load_json(STAGE9859_TICKET)
    stage9862_execution = load_json(STAGE9862_EXECUTION)
    failures: list[str] = []
    warnings: list[str] = []

    if source_9857.get("passed") is not True:
        failures.append("stage9857_not_passed")
    if source_9859.get("passed") is not True:
        failures.append("stage9859_not_passed")
    if source_9862.get("passed") is not True:
        failures.append("stage9862_not_passed")

    surface_cards: dict[str, Any] = {}
    for surface in SURFACE_SPECS:
        path = TINY_DIR / f"{surface}_tiny.jsonl"
        rows = read_jsonl(path)
        if not rows:
            failures.append(f"missing_rows:{surface}")
            continue
        card = surface_language_card(rows)
        card["manifest"] = str(path.relative_to(ROOT))
        card["mode"] = SURFACE_SPECS[surface]["mode"]
        card["expected_loss"] = SURFACE_SPECS[surface]["loss"]
        surface_cards[surface] = card

    symbol_card = surface_cards.get("symbol_binding", {})
    edit_card = surface_cards.get("edit_localization", {})
    patch_card = surface_cards.get("patch_operator_selection", {})
    verifier_card = surface_cards.get("verifier_failure_repair_or_abstain", {})

    if symbol_card.get("inferred_language_counts") == {"python": 64}:
        warnings.append("symbol_binding_v27_path_is_python_only")
    if symbol_card.get("multilingual_ready"):
        warnings.append("symbol_binding_unexpectedly_multilingual_ready")
    if not edit_card.get("multilingual_ready"):
        failures.append("edit_localization_not_multilingual_ready")
    if not patch_card.get("multilingual_ready"):
        failures.append("patch_operator_not_multilingual_ready")
    if not verifier_card.get("multilingual_ready"):
        failures.append("verifier_repair_not_multilingual_ready")

    next_command = build_next_command(ticket)
    if not next_command:
        failures.append("missing_edit_localization_surface_command")

    if next_command:
        joined = " ".join(next_command)
        if "stage9864_edit_localization_target_100m_structured_tiny_probe" not in joined:
            failures.append("stage9864_namespace_missing_from_next_command")
        if "--mode edit_localization_probe" not in joined:
            failures.append("next_command_not_edit_localization_probe")
        if "--decoder-ce-weight 0.0" not in joined:
            failures.append("next_command_decoder_ce_not_zero")

    candidate = {
        "future_stage": 9864,
        "future_stage_name": "stage9864_edit_localization_target_100m_structured_tiny_probe",
        "selected_surface": "edit_localization",
        "reason": "Stage9862 proved the repaired execution path on a Python-only symbol-binding surface; Stage9859 edit localization is the first v2.7 tiny surface with genuine multilingual coverage across python, rust, c_cpp, and web_js_ts_html.",
        "command": next_command,
        "requires_explicit_user_confirmation_before_execution": True,
        "requires_this_stage_passed": True,
        "authority": dict(AUTHORITY_CLOSED),
    }
    NEXT_CANDIDATE.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    stage9862_eval = ((stage9862_execution.get("eval") or {}).get("eval") or {}).get("field_exact") or {}
    stage9862_strict = ((stage9862_execution.get("eval") or {}).get("strict_eval") or {}).get("field_exact") or {}
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "warnings": warnings,
        "failures": failures,
        "surface_cards": surface_cards,
        "stage9862_scope": {
            "surface": "symbol_binding",
            "inferred_language_counts": symbol_card.get("inferred_language_counts"),
            "top_level_language_counts": symbol_card.get("top_level_language_counts"),
            "eval_symbol_binding_exact": ((stage9862_eval.get("symbol_binding") or {}).get("exact")),
            "strict_symbol_binding_exact": ((stage9862_strict.get("symbol_binding") or {}).get("exact")),
            "multilingual_claim_supported": False,
            "claim_guardrail": "Do not use Stage9862 as cross-language evidence; this execution path currently supports only Python symbol binding in the v2.7 tiny package.",
        },
        "source_summaries": {
            "stage9857": str(SOURCE_9857.relative_to(ROOT)),
            "stage9859": str(SOURCE_9859.relative_to(ROOT)),
            "stage9862": str(SOURCE_9862.relative_to(ROOT)),
        },
        "next_execution_candidate": str(NEXT_CANDIDATE.relative_to(ROOT)),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": "Run Stage9864 edit-localization target-100M structured tiny probe under trellis, then compare its multilingual exact rates to the existing Gemma same-surface packets before reopening any broad beat-Gemma claim.",
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": True,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "next_execution_candidate": str(NEXT_CANDIDATE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "metrics": {
            "symbol_binding_inferred_language_counts": symbol_card.get("inferred_language_counts"),
            "edit_localization_inferred_language_counts": edit_card.get("inferred_language_counts"),
            "patch_operator_inferred_language_counts": patch_card.get("inferred_language_counts"),
            "verifier_repair_inferred_language_counts": verifier_card.get("inferred_language_counts"),
            "stage9862_multilingual_claim_supported": False,
            "stage9862_strict_symbol_binding_exact": ((stage9862_strict.get("symbol_binding") or {}).get("exact")),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": audit["next_best_step"],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9863 Validity-Weighted Multilingual Surface Truthfulness Audit",
                "",
                f"Passed: `{summary['passed']}`",
                f"Warnings: `{warnings}`",
                f"Symbol binding inferred language counts: `{symbol_card.get('inferred_language_counts')}`",
                f"Edit localization inferred language counts: `{edit_card.get('inferred_language_counts')}`",
                "",
                "This audit closes a scope gap left by Stage9862: the repaired symbol-binding execution path is real, but the v2.7 tiny package currently supplies only Python rows for that surface.",
                "",
                "Edit localization, patch operator, and verifier repair tiny manifests retain cross-language coverage across python, rust, c_cpp, and web_js_ts_html, so edit localization is the next truthful multilingual execution target.",
                "",
                f"Next: {audit['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "warnings": warnings, "failures": failures, "candidate": str(NEXT_CANDIDATE.relative_to(ROOT))}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
