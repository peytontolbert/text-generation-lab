#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, symbol)


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_CLOSED = _load_symbol("stage10007_contract", ROOT / "scripts/diagnostic_ticket_contract.py", "AUTHORITY_CLOSED")
STAGE = 10007
NAME = "stage10007_attach_heldout_evidence_to_active_review_cards"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "attach_heldout_evidence_to_active_review_cards.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ATTACH_HELDOUT_EVIDENCE_TO_ACTIVE_REVIEW_CARDS_STAGE10007.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
ACTIVE_BASE = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"
COMPARISON = ROOT / "runs/summaries/stage10001_source_heldout_same_manifest_comparison_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _base(lang: str) -> Path:
    return ACTIVE_BASE / f"standalone_100m_weights__{lang}__edit_localization"


def build_refresh() -> dict[str, Any]:
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    per_language = ((load_json(COMPARISON).get("metrics") or {}).get("per_language") or {})
    for lang in LANGS:
        base = _base(lang)
        rubric_path = base / "expert_maintainer_rubric_review.json"
        anti_path = base / "anti_cheat_review_card.json"
        draft_rubric = base / "expert_maintainer_recommendation_draft.json"
        draft_anti = base / "anti_cheat_recommendation_draft.json"
        if not all(path.exists() for path in [rubric_path, anti_path, draft_rubric, draft_anti]):
            failures.append(f"missing_active_review_or_draft:{lang}")
            continue
        comparison_row = per_language.get(lang)
        if not isinstance(comparison_row, dict):
            failures.append(f"missing_comparison_metrics:{lang}")
            continue
        heldout_bundle = {
            "current_frontier_type": "source_heldout_same_manifest",
            "same_surface_rows": comparison_row.get("rows"),
            "same_surface_exact_100m": comparison_row.get("hundred_m_exact"),
            "same_surface_exact_gemma": comparison_row.get("gemma_exact"),
            "same_surface_verdict": comparison_row.get("verdict"),
            "same_surface_comparison_path": display(ROOT / "runs/local/artifacts/stage10001_source_heldout_same_manifest_comparison_audit/source_heldout_same_manifest_comparison_audit.json"),
            "same_surface_rows_100m": display(ROOT / "runs/local/artifacts/stage9998_source_heldout_target100m_probe/edit_localization_probe/row_field_logits.jsonl"),
            "same_surface_rows_gemma12b": display(ROOT / "runs/local/artifacts/stage10000_source_heldout_same_manifest_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"),
            "source_overlap_audit_path": display(ROOT / "runs/local/artifacts/stage9995_source_overlap_eval_hacking_audit/source_overlap_eval_rows.jsonl"),
            "duplicate_rowid_audit_path": display(ROOT / "runs/local/artifacts/stage10002_duplicate_rowid_eval_audit/duplicate_eval_row_ids.jsonl"),
            "deduped_successor_manifest_path": display(ROOT / "runs/local/artifacts/stage10003_deduped_source_heldout_successor_request/edit_localization_manifest.jsonl"),
        }
        rubric = load_json(rubric_path)
        rubric["current_frontier_evidence"] = heldout_bundle
        rubric["review_status"] = "pending_human_review_with_source_heldout_evidence"
        rubric["reviewer_guidance"] = list(dict.fromkeys(list(rubric.get("reviewer_guidance") or []) + [
            "This card is now aligned to the source-heldout same-manifest frontier rather than the earlier weighted-hardened comparison.",
            "Confirm that the heldout comparison and eval-hacking audits are sufficient before final rubric signoff.",
        ]))
        write_json(rubric_path, rubric)

        anti = load_json(anti_path)
        anti["current_frontier_evidence"] = heldout_bundle
        anti["review_status"] = "pending_cell_specific_review_with_source_heldout_evidence"
        anti["reviewer_guidance"] = list(dict.fromkeys(list(anti.get("reviewer_guidance") or []) + [
            "This card is now aligned to the source-heldout same-manifest frontier rather than the earlier weighted-hardened comparison.",
            "Use the attached overlap and duplicate-row audits to confirm the current eval surface is cheat-resistant before final anti-cheat signoff.",
        ]))
        write_json(anti_path, anti)

        rows.append({
            "language_family": lang,
            "cell_key": f"standalone_100m_weights::{lang}::edit_localization",
            "rubric_review": display(rubric_path),
            "anti_cheat_review": display(anti_path),
            "frontier_verdict": comparison_row.get("verdict"),
        })

    metrics = {
        "winner_cells_enriched": len(rows),
        "rubric_cards_updated": len(rows),
        "anti_cheat_cards_updated": len(rows),
    }
    if metrics["winner_cells_enriched"] != 4:
        failures.append("winner_cells_enriched_not_4")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": rows, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_refresh()
    write_json(MANIFEST, built)
    next_step = "Use the enriched active standalone winner review cards for human signoff, because each live rubric and anti-cheat file now embeds the current source-heldout evidence and eval-hardening audit references in place."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {"manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Enriched the four active standalone winner review cards so the final human-owned rubric and anti-cheat files now embed the current source-heldout comparison and eval-hardening evidence directly in place.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10007 Attach Heldout Evidence To Active Review Cards",
        "",
        f"Passed: `{summary['passed']}`",
        f"Winner cells enriched: `{summary['metrics']['winner_cells_enriched']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
