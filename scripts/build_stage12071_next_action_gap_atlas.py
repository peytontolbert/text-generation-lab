#!/usr/bin/env python3
"""Build a gap atlas for the transition_next_action bottleneck.

Stage12070 showed that repaired verifier-status routing retains the selected
transition frontier but does not improve it.  The weakest remaining transition
family is transition_next_action, so this stage joins routed audit row cards
back to the original transition projection rows and summarizes the actual
semantic confusions instead of launching another training probe.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 12071
STAGE_NAME = "stage12071_next_action_gap_atlas"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / STAGE_NAME
SUMMARY_PATH = ROOT / "runs" / "summaries" / f"{STAGE_NAME}.json"

BASELINE_AUDIT = (
    ROOT
    / "runs/local/artifacts/stage12069_transition_status_head_repaired_options_composite_audit"
    / "stage11924_baseline_semantic_route"
    / "bounded_choice_eval_audit_stage11924_baseline_transition_projection__semantic_candidate_head.json"
)
STAGE12068_SEMANTIC_AUDIT = (
    ROOT
    / "runs/local/artifacts/stage12069_transition_status_head_repaired_options_composite_audit"
    / "stage12068_semantic_route"
    / "bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json"
)
STAGE12068_STATUS_AUDIT = (
    ROOT
    / "runs/local/artifacts/stage12069_transition_status_head_repaired_options_composite_audit"
    / "stage12068_status_route"
    / "bounded_choice_eval_audit_transition_projection__transition_status_head.json"
)
SOURCE_ROWS = (
    ROOT
    / "runs/local/artifacts/stage11897_transition_record_projection_rows"
    / "transition_projection_rows.jsonl"
)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def option_value(row: dict[str, Any], label: str | None) -> str | None:
    if not label:
        return None
    opts = row.get("standalone_projection_source", {}).get("opaque_options")
    if not opts:
        opts = row.get("opaque_options") or []
    for opt in opts:
        if opt.get("label") == label:
            return opt.get("value")
    return None


def option_role(row: dict[str, Any], label: str | None) -> str | None:
    if not label:
        return None
    opts = row.get("standalone_projection_source", {}).get("opaque_options")
    if not opts:
        opts = row.get("opaque_options") or []
    for opt in opts:
        if opt.get("label") == label:
            return opt.get("role")
    return None


def short_root(row: dict[str, Any]) -> str:
    root_id = row.get("root_id") or row.get("root_lineage_key") or ""
    parts = root_id.split("::")
    if len(parts) >= 2:
        return "::".join(parts[:2])
    return root_id


def source_record(row_id: str) -> str:
    parts = row_id.split("::")
    if len(parts) >= 2:
        return "::".join(parts[:-1])
    return row_id


def load_source_rows() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(SOURCE_ROWS):
        rid = row["row_id"]
        rows[rid] = row
    return rows


def load_cards(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(path)
    return {card["row_id"]: card for card in payload["row_cards"]}


def top(counter: Counter, n: int = 20) -> list[dict[str, Any]]:
    return [{"key": k, "count": v} for k, v in counter.most_common(n)]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    source_rows = load_source_rows()
    baseline = load_cards(BASELINE_AUDIT)
    stage12068_semantic = load_cards(STAGE12068_SEMANTIC_AUDIT)
    stage12068_status = load_cards(STAGE12068_STATUS_AUDIT)

    next_action_rows: list[dict[str, Any]] = []
    missing_source: list[str] = []
    for row_id, card in baseline.items():
        if not row_id.endswith("::next_action"):
            continue
        row = source_rows.get(row_id)
        if not row:
            missing_source.append(row_id)
            continue
        pred_label = card.get("constrained_choice_top1_label")
        target_label = card.get("bounded_choice_target_label")
        enriched = {
            "row_id": row_id,
            "root_id": row.get("root_id"),
            "root_family": short_root(row),
            "repo_id": row.get("repo_id"),
            "language_family": row.get("language_family"),
            "task_family": row.get("task_type"),
            "source_record_id": source_record(row_id),
            "target_label": target_label,
            "target_value": option_value(row, target_label),
            "target_role": option_role(row, target_label),
            "baseline_pred_label": pred_label,
            "baseline_pred_value": option_value(row, pred_label),
            "baseline_pred_role": option_role(row, pred_label),
            "baseline_match": bool(card.get("constrained_choice_match")),
            "target_rank_full_vocab": card.get("target_rank_full_vocab"),
            "full_vocab_top1_text": card.get("full_vocab_top1_text"),
            "stage12068_semantic_pred_label": stage12068_semantic.get(row_id, {}).get(
                "constrained_choice_top1_label"
            ),
            "stage12068_semantic_match": bool(
                stage12068_semantic.get(row_id, {}).get("constrained_choice_match")
            ),
            "stage12068_status_pred_label": stage12068_status.get(row_id, {}).get(
                "constrained_choice_top1_label"
            ),
            "stage12068_status_match": bool(
                stage12068_status.get(row_id, {}).get("constrained_choice_match")
            ),
            "observed_status": None,
            "checks": None,
        }
        text = row.get("input_text") or row.get("prompt_text") or ""
        for line in text.splitlines():
            if line.startswith("observed_status:"):
                enriched["observed_status"] = line.split(":", 1)[1].strip()
            elif line.startswith("checks:"):
                enriched["checks"] = line.split(":", 1)[1].strip()
        next_action_rows.append(enriched)

    misses = [r for r in next_action_rows if not r["baseline_match"]]
    correct = [r for r in next_action_rows if r["baseline_match"]]

    by_target = Counter(r["target_value"] for r in misses)
    by_pred = Counter(r["baseline_pred_value"] for r in misses)
    by_confusion = Counter((r["target_value"], r["baseline_pred_value"]) for r in misses)
    by_language = Counter(r["language_family"] for r in misses)
    by_root_family = Counter(r["root_family"] for r in misses)
    by_status = Counter(r["observed_status"] for r in misses)
    by_full_vocab_rank = Counter(
        "rank1"
        if r["target_rank_full_vocab"] == 1
        else "rank2_5"
        if isinstance(r["target_rank_full_vocab"], int) and r["target_rank_full_vocab"] <= 5
        else "rank6_50"
        if isinstance(r["target_rank_full_vocab"], int) and r["target_rank_full_vocab"] <= 50
        else "rank_gt50_or_missing"
        for r in misses
    )

    corrected_by_12068_semantic = [
        r for r in misses if r["stage12068_semantic_match"] and not r["baseline_match"]
    ]
    regressed_by_12068_semantic = [
        r
        for r in correct
        if not r["stage12068_semantic_match"]
    ]
    corrected_by_12068_status = [
        r for r in misses if r["stage12068_status_match"] and not r["baseline_match"]
    ]
    regressed_by_12068_status = [
        r
        for r in correct
        if not r["stage12068_status_match"]
    ]

    miss_rows_path = OUT_DIR / "transition_next_action_miss_rows.jsonl"
    with miss_rows_path.open("w", encoding="utf-8") as f:
        for row in misses:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    all_rows_path = OUT_DIR / "transition_next_action_all_rows.jsonl"
    with all_rows_path.open("w", encoding="utf-8") as f:
        for row in next_action_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    confusion_path = OUT_DIR / "transition_next_action_confusions.json"
    confusion_payload = [
        {"target_value": k[0], "pred_value": k[1], "count": v}
        for k, v in by_confusion.most_common()
    ]
    with confusion_path.open("w", encoding="utf-8") as f:
        json.dump(confusion_payload, f, indent=2, sort_keys=True)
        f.write("\n")

    priority_confusions = [
        item
        for item in confusion_payload
        if item["count"] >= 5
        or item["target_value"] in {"VERIFY_RESULT", "REPAIR_AFTER_FAILURE", "PLAN_PATCH"}
    ][:20]

    recommendation = {
        "recommended_stage": "stage12072_next_action_support_design",
        "do_not_train_yet": True,
        "reason": "The atlas should drive targeted next-action support rows; status/verifier support already retained but did not improve the frontier.",
        "target_row_geometry": [
            "root-local action candidates with identical labels but varied verifier state",
            "counterfactuals where SELECT_TEST, VERIFY_RESULT, PLAN_PATCH, REPAIR_AFTER_FAILURE, and ABSTAIN_OR_ROLLBACK are each correct",
            "explicit milestone/state fields showing whether evidence is pre-test, post-test, post-failure, or completion-gate",
            "same-root hard negatives for premature patching and premature verification",
        ],
        "minimum_support_before_probe": {
            "transition_next_action_rows": 200,
            "unique_roots": 80,
            "per_target_floor": {
                "SELECT_TEST": 20,
                "VERIFY_RESULT": 20,
                "PLAN_PATCH": 20,
                "REPAIR_AFTER_FAILURE": 20,
                "ABSTAIN_OR_ROLLBACK": 20,
            },
            "language_floor_roots_each": 15,
        },
    }

    summary = {
        "stage": STAGE,
        "stage_name": STAGE_NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_artifacts": {
            "baseline_audit": str(BASELINE_AUDIT.relative_to(ROOT)),
            "stage12068_semantic_audit": str(STAGE12068_SEMANTIC_AUDIT.relative_to(ROOT)),
            "stage12068_status_audit": str(STAGE12068_STATUS_AUDIT.relative_to(ROOT)),
            "source_rows": str(SOURCE_ROWS.relative_to(ROOT)),
        },
        "coverage": {
            "next_action_rows": len(next_action_rows),
            "baseline_correct": len(correct),
            "baseline_misses": len(misses),
            "missing_source_rows": len(missing_source),
        },
        "baseline_accuracy": len(correct) / len(next_action_rows) if next_action_rows else 0.0,
        "miss_buckets": {
            "by_target_value": top(by_target),
            "by_pred_value": top(by_pred),
            "by_confusion": confusion_payload[:30],
            "by_language": top(by_language),
            "by_root_family": top(by_root_family),
            "by_observed_status": top(by_status),
            "by_full_vocab_target_rank_bucket": top(by_full_vocab_rank),
        },
        "stage12068_comparison": {
            "semantic_route_corrected_baseline_misses": len(corrected_by_12068_semantic),
            "semantic_route_regressed_baseline_correct": len(regressed_by_12068_semantic),
            "status_route_corrected_baseline_misses": len(corrected_by_12068_status),
            "status_route_regressed_baseline_correct": len(regressed_by_12068_status),
        },
        "priority_confusions_for_support_design": priority_confusions,
        "interpretation": [
            "transition_next_action is the weakest old-transition family and should be the next data/objective target.",
            "Stage12068 status routing is not a next-action fix; use it only as evidence that status-head plumbing works.",
            "The next probe should not run until support rows explicitly cover the dominant next-action confusions.",
        ],
        "recommendation": recommendation,
        "outputs": {
            "all_rows": str(all_rows_path.relative_to(ROOT)),
            "miss_rows": str(miss_rows_path.relative_to(ROOT)),
            "confusions": str(confusion_path.relative_to(ROOT)),
            "summary": str((OUT_DIR / "next_action_gap_atlas.json").relative_to(ROOT)),
            "summary_mirror": str(SUMMARY_PATH.relative_to(ROOT)),
        },
    }

    summary_path = OUT_DIR / "next_action_gap_atlas.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
