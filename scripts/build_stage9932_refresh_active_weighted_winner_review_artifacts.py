#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9932
NAME = "stage9932_refresh_active_weighted_winner_review_artifacts"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "refresh_active_weighted_winner_review_artifacts.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REFRESH_ACTIVE_WEIGHTED_WINNER_REVIEW_ARTIFACTS_STAGE9932.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_DIR = ROOT / "runs/local/artifacts/stage9921_hardened_weighted_multilingual_winner_review_packets/review_packets"
TARGET_DIR = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


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


def _source_base(lang: str) -> Path:
    return SOURCE_DIR / f"hardened_weighted_same_surface__{lang}__edit_localization"


def _target_base(lang: str) -> Path:
    return TARGET_DIR / f"standalone_100m_weights__{lang}__edit_localization"


def _retarget_payload(payload: dict[str, Any], *, lang: str, target_base: Path) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    source_cell = f"hardened_weighted_same_surface::{lang}::edit_localization"
    target_cell = f"standalone_100m_weights::{lang}::edit_localization"
    source_slug = f"hardened_weighted_same_surface__{lang}__edit_localization"
    target_slug = f"standalone_100m_weights__{lang}__edit_localization"

    def rewrite(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace(source_cell, target_cell).replace(source_slug, target_slug)
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        return value

    out = rewrite(out)
    out["cell_key"] = target_cell
    out["language_family"] = lang
    out["packet_dir"] = display(target_base)
    out["authority"] = dict(AUTHORITY_CLOSED)
    return out


def build_refresh() -> dict[str, Any]:
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    for lang in LANGS:
        source_base = _source_base(lang)
        target_base = _target_base(lang)
        needed = {
            "rubric": source_base / "expert_maintainer_rubric_review.json",
            "anti": source_base / "anti_cheat_review_card.json",
            "rubric_draft": source_base / "expert_maintainer_recommendation_draft.json",
            "anti_draft": source_base / "anti_cheat_recommendation_draft.json",
        }
        if not all(path.exists() for path in needed.values()):
            failures.append(f"missing_source_review_artifacts:{lang}")
            continue
        rubric = _retarget_payload(load_json(needed["rubric"]), lang=lang, target_base=target_base)
        anti = _retarget_payload(load_json(needed["anti"]), lang=lang, target_base=target_base)
        rubric_draft = _retarget_payload(load_json(needed["rubric_draft"]), lang=lang, target_base=target_base)
        anti_draft = _retarget_payload(load_json(needed["anti_draft"]), lang=lang, target_base=target_base)

        rubric["status"] = "pending_human_review_with_weighted_hardened_evidence"
        rubric["required_human_action"] = "review the attached weighted hardened same-surface evidence and confirm final expert-maintainer rubric judgments"
        rubric["draft_recommendation_path"] = display(target_base / "expert_maintainer_recommendation_draft.json")
        rubric["reviewer_guidance"] = [
            "This active standalone winner packet is now aligned to the weighted hardened multilingual frontier.",
            "The attached recommendation draft is machine-generated support only and must not be treated as final human signoff.",
        ]

        anti["status"] = "pending_cell_specific_review_with_weighted_hardened_evidence"
        anti["required_human_action"] = "review the attached weighted hardened anti-cheat evidence and confirm final challenge-family judgments"
        anti["draft_recommendation_path"] = display(target_base / "anti_cheat_recommendation_draft.json")
        anti["reviewer_guidance"] = [
            "This active standalone winner packet is now aligned to the weighted hardened multilingual frontier.",
            "The attached anti-cheat recommendation draft is machine-generated support only and must not be treated as final human signoff.",
        ]

        write_json(target_base / "expert_maintainer_rubric_review.json", rubric)
        write_json(target_base / "anti_cheat_review_card.json", anti)
        write_json(target_base / "expert_maintainer_recommendation_draft.json", rubric_draft)
        write_json(target_base / "anti_cheat_recommendation_draft.json", anti_draft)

        rows.append({
            "language_family": lang,
            "cell_key": f"standalone_100m_weights::{lang}::edit_localization",
            "target_dir": display(target_base),
            "rubric_review": display(target_base / "expert_maintainer_rubric_review.json"),
            "anti_cheat_review": display(target_base / "anti_cheat_review_card.json"),
            "rubric_draft": display(target_base / "expert_maintainer_recommendation_draft.json"),
            "anti_cheat_draft": display(target_base / "anti_cheat_recommendation_draft.json"),
        })

    metrics = {
        "winner_cells_refreshed": len(rows),
        "rubric_review_files_refreshed": len(rows),
        "anti_cheat_review_files_refreshed": len(rows),
        "recommendation_drafts_copied": len(rows) * 2,
    }
    if metrics["winner_cells_refreshed"] != 4:
        failures.append("winner_cells_refreshed_not_4")
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
        "Use the refreshed active standalone winner packet dirs for human signoff, because the live expert-rubric and anti-cheat files now align to the weighted hardened multilingual frontier and include machine recommendation drafts in-place."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {"manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Refreshed the four active standalone weighted winner review packet dirs so their live rubric and anti-cheat files now point at the weighted hardened multilingual frontier and include recommendation drafts beside the final review targets.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9932 Refresh Active Weighted Winner Review Artifacts",
        "",
        f"Passed: `{summary['passed']}`",
        f"Winner cells refreshed: `{summary['metrics']['winner_cells_refreshed']}`",
        f"Recommendation drafts copied: `{summary['metrics']['recommendation_drafts_copied']}`",
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
