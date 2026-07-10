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
STAGE = 9933
NAME = "stage9933_attach_weighted_recommendations_to_active_review_cards"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "attach_weighted_recommendations_to_active_review_cards.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ATTACH_WEIGHTED_RECOMMENDATIONS_TO_ACTIVE_REVIEW_CARDS_STAGE9933.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
ACTIVE_BASE = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"


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
    for lang in LANGS:
        base = _base(lang)
        rubric_path = base / "expert_maintainer_rubric_review.json"
        rubric_draft_path = base / "expert_maintainer_recommendation_draft.json"
        anti_path = base / "anti_cheat_review_card.json"
        anti_draft_path = base / "anti_cheat_recommendation_draft.json"
        if not all(path.exists() for path in [rubric_path, rubric_draft_path, anti_path, anti_draft_path]):
            failures.append(f"missing_active_review_or_draft:{lang}")
            continue
        rubric = load_json(rubric_path)
        rubric_draft = load_json(rubric_draft_path)
        anti = load_json(anti_path)
        anti_draft = load_json(anti_draft_path)

        rubric["recommended_subskills"] = dict(rubric_draft.get("recommended_subskills") or {})
        rubric["recommendation_reviewer_message"] = str(rubric_draft.get("reviewer_message") or "")
        rubric["recommendation_source_path"] = display(rubric_draft_path)
        rubric["auto_review_complete"] = False
        rubric["reviewer_guidance"] = list(dict.fromkeys(list(rubric.get("reviewer_guidance") or []) + [
            "Use the attached recommended_subskills only as a draft; final judgments remain human-owned.",
        ]))
        write_json(rubric_path, rubric)

        recommended = anti_draft.get("recommended_challenge_judgments") or []
        recommended_index = {str(row.get("challenge_family") or ""): row for row in recommended if isinstance(row, dict)}
        challenge_rows = []
        for existing in anti.get("challenge_families") or []:
            if not isinstance(existing, dict):
                continue
            merged = dict(existing)
            draft_row = recommended_index.get(str(existing.get("challenge_family") or ""))
            if isinstance(draft_row, dict):
                merged["recommended_pass"] = draft_row.get("recommended_pass")
                merged["recommendation_confidence"] = draft_row.get("confidence")
                merged["recommendation_notes"] = list(draft_row.get("reviewer_notes") or [])
                merged["present"] = False
            challenge_rows.append(merged)
        anti["challenge_families"] = challenge_rows
        anti["recommendation_reviewer_message"] = str(anti_draft.get("reviewer_message") or "")
        anti["recommendation_source_path"] = display(anti_draft_path)
        anti["reviewer_guidance"] = list(dict.fromkeys(list(anti.get("reviewer_guidance") or []) + [
            "Use the challenge-family recommendations only as a draft; final anti-cheat judgments remain human-owned.",
        ]))
        write_json(anti_path, anti)

        rows.append({
            "language_family": lang,
            "cell_key": f"standalone_100m_weights::{lang}::edit_localization",
            "rubric_review": display(rubric_path),
            "anti_cheat_review": display(anti_path),
            "recommended_subskills": len(rubric.get("recommended_subskills") or {}),
            "recommended_challenge_families": len(anti.get("challenge_families") or []),
        })

    metrics = {
        "winner_cells_enriched": len(rows),
        "rubric_cards_with_recommendations": sum(1 for row in rows if row["recommended_subskills"] > 0),
        "anti_cheat_cards_with_recommendations": sum(1 for row in rows if row["recommended_challenge_families"] > 0),
    }
    if metrics["winner_cells_enriched"] != 4:
        failures.append("winner_cells_enriched_not_4")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "rows": rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_refresh()
    write_json(MANIFEST, built)
    next_step = (
        "Use the enriched active standalone winner review cards for human signoff, because each live rubric and anti-cheat file now includes the weighted hardened recommendation content directly beside the final human-owned fields."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {"manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Enriched the four active standalone weighted winner review cards so the final human-owned rubric and anti-cheat files now embed the weighted hardened recommendation content and source references in place.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9933 Attach Weighted Recommendations To Active Review Cards",
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
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
