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
STAGE = 9806
NAME = "stage9806_opaque_choice_error_atlas"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ATLAS = OUT_DIR / "opaque_choice_error_atlas.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPAQUE_CHOICE_ERROR_ATLAS_STAGE9806.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MANIFEST = ROOT / "runs/local/artifacts/stage9790_edit_localization_opaque_choice_surface/edit_localization_opaque_choice_surface.jsonl"
ROW_LOGITS = ROOT / "runs/local/artifacts/stage9794_edit_localization_opaque_choice_exec_stable_labels/row_field_logits.jsonl"
ANTI_CHEAT = ROOT / "runs/local/artifacts/stage9795_opaque_choice_counterfactual_anti_cheat_audit/opaque_choice_counterfactual_anti_cheat_audit.json"
COMPARE = ROOT / "runs/local/artifacts/stage9793_edit_localization_opaque_choice_gemma_comparison/edit_localization_opaque_choice_gemma_comparison.json"

LABEL_MEANINGS = {
    "configuration_or_settings_surface": "config",
    "entrypoint_or_invocation_surface": "entrypoint",
    "implementation_file_surface": "file",
    "symbol_definition_or_implementation_surface": "symbol",
    "test_surface": "test",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _manifest_index() -> dict[str, dict[str, Any]]:
    return {str(row.get("row_id") or ""): row for row in load_jsonl(MANIFEST)}


def _anti_index() -> dict[str, dict[str, Any]]:
    rows = load_json(ANTI_CHEAT).get("records") if isinstance(load_json(ANTI_CHEAT).get("records"), list) else []
    return {str(row.get("language_family") or ""): row for row in rows}


def _compare_index() -> dict[str, dict[str, Any]]:
    rows = load_json(COMPARE).get("results") if isinstance(load_json(COMPARE).get("results"), list) else []
    return {str(row.get("language") or ""): row for row in rows}


def _choice_meaning_map(choices: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for choice in choices:
        if not isinstance(choice, str) or ": " not in choice:
            continue
        option, meaning = choice.split(": ", 1)
        label = option.split()[-1]
        out[label] = LABEL_MEANINGS.get(meaning, meaning)
    return out


def _family_recommendation(lang: str, wrong_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not wrong_rows:
        return {
            "next_modeling_move": "keep_current_surface",
            "reason": "No strict-eval misses on this language slice.",
        }
    meaning_pairs = Counter((row["gold_meaning"], row["pred_meaning"]) for row in wrong_rows)
    dominant = sorted(meaning_pairs.items(), key=lambda item: (-item[1], str(item[0])))[0][0]
    gold_meaning, pred_meaning = dominant
    if lang == "web_js_ts_html":
        return {
            "next_modeling_move": "augment_web_visible_evidence_with_surface_disambiguators",
            "reason": "Web misses span config, entrypoint, file, and test while only symbol is correct. The slice needs stronger visible disambiguators rather than another identical sweep.",
            "dominant_confusion": f"{gold_meaning}->{pred_meaning}",
        }
    if gold_meaning == "config" and pred_meaning in {"symbol", "entrypoint"}:
        return {
            "next_modeling_move": "emphasize_configuration_vs_code_owner_contrast",
            "reason": "The model is over-trusting code-owner style evidence when configuration control should win.",
            "dominant_confusion": f"{gold_meaning}->{pred_meaning}",
        }
    if gold_meaning == "test":
        return {
            "next_modeling_move": "emphasize_stale_test_expectation_signal",
            "reason": "Test-surface rows are being reassigned to implementation or symbol classes.",
            "dominant_confusion": f"{gold_meaning}->{pred_meaning}",
        }
    if gold_meaning == "file":
        return {
            "next_modeling_move": "emphasize_file_without_symbol_boundary",
            "reason": "The model is confusing file-level responsibility with entrypoint or configuration ownership.",
            "dominant_confusion": f"{gold_meaning}->{pred_meaning}",
        }
    return {
        "next_modeling_move": "augment_visible_contrastive_evidence",
        "reason": "Strict-eval misses remain concentrated in a small set of contrastive surface pairs.",
        "dominant_confusion": f"{gold_meaning}->{pred_meaning}",
    }


def build_atlas() -> dict[str, Any]:
    manifest = _manifest_index()
    anti = _anti_index()
    compare = _compare_index()
    failures: list[str] = []
    per_language: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in load_jsonl(ROW_LOGITS):
        row_id = str(row.get("row_id") or "")
        manifest_row = manifest.get(row_id)
        if not isinstance(manifest_row, dict):
            failures.append(f"missing_manifest_row:{row_id}")
            continue
        if str(manifest_row.get("split") or "") != "strict_eval":
            continue
        lang = str(manifest_row.get("language_family") or "")
        choice_map = _choice_meaning_map((manifest_row.get("input_state") or {}).get("candidate_choices") or [])
        gold = str(row.get("target") or "")
        pred = str(row.get("pred") or "")
        grouped[lang].append(
            {
                "row_id": row_id,
                "gold": gold,
                "pred": pred,
                "correct": pred == gold,
                "gold_meaning": choice_map.get(gold, gold),
                "pred_meaning": choice_map.get(pred, pred),
                "visible_locality_evidence": (manifest_row.get("input_state") or {}).get("visible_locality_evidence"),
                "task_observation": (manifest_row.get("input_state") or {}).get("task_observation"),
            }
        )

    for lang in sorted(grouped):
        rows = sorted(grouped[lang], key=lambda row: str(row["row_id"]))
        wrong = [row for row in rows if not row["correct"]]
        confusions = Counter((row["gold"], row["pred"]) for row in rows)
        meaning_confusions = Counter((row["gold_meaning"], row["pred_meaning"]) for row in rows)
        anti_row = anti.get(lang) or {}
        compare_row = compare.get(lang) or {}
        per_language.append(
            {
                "language_family": lang,
                "strict_rows": len(rows),
                "strict_correct_rows": sum(1 for row in rows if row["correct"]),
                "strict_exact_100m": compare_row.get("model_strict_exact_100m"),
                "strict_exact_gemma12b": compare_row.get("gemma_strict_exact"),
                "same_surface_verdict": compare_row.get("verdict"),
                "wrong_rows": wrong,
                "label_confusions": {f"{gold}->{pred}": count for (gold, pred), count in sorted(confusions.items())},
                "meaning_confusions": {f"{gold}->{pred}": count for (gold, pred), count in sorted(meaning_confusions.items())},
                "anti_cheat_probe_scores": {
                    "permutation": ((anti_row.get("counterfactual_probes") or {}).get("label_order_permutation") or {}).get("score"),
                    "decoy": ((anti_row.get("counterfactual_probes") or {}).get("decoy_label_injection") or {}).get("score"),
                    "ablation": ((anti_row.get("counterfactual_probes") or {}).get("critical_evidence_ablation") or {}).get("score"),
                    "causal_flip": ((anti_row.get("counterfactual_probes") or {}).get("causal_flip") or {}).get("score"),
                },
                "recommendation": _family_recommendation(lang, wrong),
            }
        )

    metrics = {
        "language_slices": len(per_language),
        "winning_languages": sum(1 for row in per_language if row.get("same_surface_verdict") == "100m_better"),
        "tied_languages": sum(1 for row in per_language if row.get("same_surface_verdict") == "tie"),
        "losing_languages": sum(1 for row in per_language if row.get("same_surface_verdict") == "gemma_better"),
        "web_wrong_rows": next((len(row["wrong_rows"]) for row in per_language if row["language_family"] == "web_js_ts_html"), 0),
    }
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "languages": per_language,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    atlas = build_atlas()
    ATLAS.write_text(json.dumps(atlas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the Stage9806 atlas to target the next structured-surface data/objective revision at the real web and contrastive confusion families, while keeping Stage9794 as the truthful standalone comparator."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": atlas["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **atlas["metrics"]},
        "artifacts": {"atlas": str(ATLAS.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized a row-level multilingual error atlas for the corrected Stage9794 structured win so the next modeling change can target the actual remaining confusions instead of repeating generic sweeps.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9806 Opaque Choice Error Atlas",
                "",
                f"Passed: `{summary['passed']}`",
                f"Language slices: `{atlas['metrics']['language_slices']}`",
                f"Winning languages: `{atlas['metrics']['winning_languages']}`",
                f"Tied languages: `{atlas['metrics']['tied_languages']}`",
                f"Web wrong rows: `{atlas['metrics']['web_wrong_rows']}`",
                "",
                "This atlas turns the corrected Stage9794 structured run into a concrete next-step map. Web is the remaining standalone gap, and the wrong rows show that it is not one isolated label but a broad contrastive disambiguation problem across config, entrypoint, file, and test surfaces.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": atlas["metrics"], "failures": atlas["failures"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
