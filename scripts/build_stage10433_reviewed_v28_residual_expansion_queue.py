#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10433
NAME = "stage10433_reviewed_v28_residual_expansion_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE_JSON = OUT_DIR / "reviewed_v28_residual_expansion_queue.json"
ROWS_JSONL = OUT_DIR / "reviewed_v28_residual_expansion_targets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

MARGIN_JSON = ROOT / "runs/local/artifacts/stage10431_reviewed_v27_saved_runtime_margin_audit/reviewed_v27_saved_runtime_margin_audit.json"
SCALING_ATLAS_JSON = ROOT / "runs/local/artifacts/stage10417_multilingual_reviewed_scaling_atlas/multilingual_reviewed_scaling_atlas.json"
PYTHON_REPLENISH_JSON = ROOT / "runs/local/artifacts/stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_execution_request.json"
RUST_FLASH_JSON = ROOT / "runs/local/artifacts/stage10416_ai_adjudicate_rust_flash_attn_bundle/rust_flash_attn_ai_adjudication_summary.json"
WEB_GAP_JSON = ROOT / "runs/local/artifacts/stage10418_pure_web_verifier_anchor_gap_audit/pure_web_verifier_anchor_gap_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    margin = load_json(MARGIN_JSON)
    atlas = load_json(SCALING_ATLAS_JSON)
    python_supply = load_json(PYTHON_REPLENISH_JSON)
    rust_supply = load_json(RUST_FLASH_JSON)
    web_gap = load_json(WEB_GAP_JSON)

    residual_rows = margin["residual_rows"]
    targets: list[dict[str, Any]] = []
    for residual in residual_rows:
        lang = residual["language_family"]
        task_type = residual["task_type"]
        if lang == "python":
            supply_status = "fresh_support_available"
            supply_artifact = display(PYTHON_REPLENISH_JSON)
            next_step = "compile disjoint Mirrormind-style verifier target competition roots and keep them out of current strict eval until reviewed"
            support_shape = [
                "multiple similar selected-test candidates",
                "visible verifier/test evidence that discriminates the gold test file",
                "no verbatim target path leakage before options",
            ]
        elif lang == "rust":
            supply_status = "fresh_support_constrained"
            supply_artifact = display(RUST_FLASH_JSON)
            next_step = "source or build new Rust evidence-citation roots beyond flash-attn, because current reviewed fresh Rust supply is abstention-heavy and not aligned to the tokenizers citation failure"
            support_shape = [
                "evidence citation rows where candidate_change_surface is a tempting negative",
                "gold support fact distinct from verifier/test constraint",
                "selected-test or trace anchor retained without exposing the answer token verbatim",
            ]
        else:
            supply_status = "unknown"
            supply_artifact = ""
            next_step = "review manually"
            support_shape = []
        targets.append(
            {
                "row_id": residual["row_id"],
                "language_family": lang,
                "task_type": task_type,
                "repo_family": residual["repo_family"],
                "residual_family": residual["residual_family"],
                "margin_top1_minus_top2": residual["margin_top1_minus_top2"],
                "selected_test_anchor": residual["selected_test_anchor"],
                "verifier_anchor": residual["verifier_anchor"],
                "prompt_target_leak": residual["prompt_target_leak"],
                "supply_status": supply_status,
                "supply_artifact": supply_artifact,
                "recommended_next_step": next_step,
                "required_support_shape": support_shape,
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Fresh reviewed-root expansion queue for moving from v2.7 same-manifest strength toward a broader v2.8 reviewed package.",
            "Targets come from the saved-runtime residual audit and are intended to replace replay-based recovery with disjoint reviewed roots.",
            "This queue keeps standalone benchmark improvement and eval hardening aligned: fresh support for real misses, plus continued web and Rust supply expansion.",
        ],
        "source_artifacts": {
            "margin_audit": display(MARGIN_JSON),
            "reviewed_scaling_atlas": display(SCALING_ATLAS_JSON),
            "python_replenishment": display(PYTHON_REPLENISH_JSON),
            "rust_flash_attn": display(RUST_FLASH_JSON),
            "pure_web_gap": display(WEB_GAP_JSON),
        },
        "summary": {
            "residual_targets": len(targets),
            "python_targets": sum(1 for row in targets if row["language_family"] == "python"),
            "rust_targets": sum(1 for row in targets if row["language_family"] == "rust"),
            "current_reviewed_bundle_count": len(atlas.get("admitted_bundle_rows") or []),
            "web_gap_still_open": True,
        },
        "targets": targets,
        "v28_priority_order": [
            "fresh Python verifier target disambiguation roots from disjoint Mirrormind-style supply",
            "fresh Rust evidence-citation contrast roots that are not abstention-heavy and not derivative of the tokenizers root",
            "pure-web verifier-anchored reviewed roots to reduce dependence on the current limited web supply",
        ],
        "dataset_requirements": [
            "split by root, not row",
            "no same-root replay into train for current strict misses",
            "explicit anti-cheat review before any new strict promotion",
            "track margins alongside exact accuracy on the expanded package",
        ],
        "web_gap_note": web_gap.get("claim_boundary") or web_gap.get("next_best_step"),
        "outputs": {
            "queue_json": display(QUEUE_JSON),
            "queue_rows": display(ROWS_JSONL),
        },
    }

    write_json(QUEUE_JSON, payload)
    write_jsonl(ROWS_JSONL, targets)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
