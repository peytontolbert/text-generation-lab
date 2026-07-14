#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11573
NAME = "stage11573_web_remaining_miss_materialization_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_remaining_miss_materialization_audit.json"

WEB_ROWS = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
STAGE11571 = SUMMARIES / "stage11571_semantic_web_hybrid_postrun_audit.json"
STAGE11549 = SUMMARIES / "stage11549_web_root_heldout_same_manifest_gemma_comparison.json"

SELECTED_FRONTIER = "stage11507+encoder_option_retrieval_evidence_judgment_head"
CURRENT_WEB_POLICY = "stage11571_semantic_web_hybrid_policy"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def task_from_row(row: dict[str, Any]) -> str:
    task = str(row.get("task_type") or "")
    if task:
        return task
    parts = str(row.get("row_id") or "").split("::")
    if len(parts) >= 2 and parts[-1] in {"heldout_v1", "train_v1"}:
        return parts[-2]
    return parts[-1] if parts else "unknown"


def repo_bucket(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(k) or "") for k in ("row_id", "repo_family", "root_id"))
    if "llama_stack" in text:
        return "llama_stack"
    if "openhands" in text:
        return "openhands"
    if "mcp_typescript" in text or "@modelcontextprotocol" in text:
        return "mcp_typescript_sdk"
    if "sep_automation" in text:
        return "sep_automation"
    return str(row.get("repo_family") or "other")


def options_for(row: dict[str, Any]) -> list[dict[str, Any]]:
    source = row.get("standalone_projection_source") or {}
    options = source.get("opaque_options") or row.get("opaque_options") or []
    return [dict(opt) for opt in options]


def option_by_label(row: dict[str, Any], label: str | None) -> dict[str, Any] | None:
    if label is None:
        return None
    for option in options_for(row):
        if str(option.get("label")) == str(label):
            return option
    return None


def compact_option(option: dict[str, Any] | None) -> dict[str, Any] | None:
    if option is None:
        return None
    text = str(option.get("text") or "")
    return {
        "label": option.get("label"),
        "value": option.get("value"),
        "text": text[:500],
        "text_len": len(text),
    }


def prompt_preview(row: dict[str, Any]) -> str:
    text = str(row.get("input_text") or row.get("prompt_text") or "")
    return text[:1200]


def classify_missing_signal(row: dict[str, Any], miss: dict[str, Any]) -> tuple[str, list[str], str]:
    bucket = repo_bucket(row)
    task = task_from_row(row)
    target_option = option_by_label(row, str(miss.get("target")))
    predicted_option = option_by_label(row, str(miss.get("predicted")))
    target_value = str((target_option or {}).get("value") or row.get("semantic_target_value") or "")
    predicted_value = str((predicted_option or {}).get("value") or "")

    flags: list[str] = []
    if bucket == "llama_stack":
        flags.extend(["no_llama_train_root_in_current_web_support", "all_tasks_missed_for_root"])
        return (
            "missing_family_transfer_signal",
            flags,
            "materialize_llama_stack_train_analogues_with_selected_tests_and_root_disjoint_options",
        )

    if bucket == "openhands" and task != "evidence_citation":
        flags.extend(["openhands_non_evidence_transfer_failure", "same_family_support_did_not_transfer"])
        if task in {"verifier_outcome", "minimal_fix_selection", "patch_impact", "abstention_insufficient_evidence"}:
            flags.append("needs_verifier_transition_or_patch_impact_supervision")
        return (
            "missing_non_evidence_transition_signal",
            flags,
            "materialize_diverse_openhands_transition_roots_with_test_ids_and_fail_pass_labels",
        )

    if task == "evidence_citation":
        flags.append("evidence_role_boundary_failure")
        if target_value and predicted_value and target_value != predicted_value:
            flags.append(f"semantic_confusion:{predicted_value}-> {target_value}")
        if bucket in {"mcp_typescript_sdk", "sep_automation"}:
            flags.append("text_rich_gate_still_misses_mcp_sep")
            return (
                "evidence_judgment_bridge_gap",
                flags,
                "build_all_supported_evidence_item_judgment_rows_with_decisive_vs_distractor_labels",
            )
        return (
            "evidence_role_boundary_gap",
            flags,
            "materialize_fresh_evidence_role_analogues_with_candidate_change_vs_verifier_constraint",
        )

    return (
        "unclassified_web_transfer_gap",
        flags,
        "inspect_row_manually_before_training",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = {row["row_id"]: row for row in load_jsonl(WEB_ROWS)}
    stage11571 = load_json(STAGE11571)
    stage11549 = load_json(STAGE11549)

    web_result = stage11571["results"]["rowsets"]["web_heldout"]["gated"]
    misses = list(web_result.get("misses") or [])
    gemma_miss_ids = {m.get("row_id") for m in (stage11549.get("gemma_misses") or [])}

    cards: list[dict[str, Any]] = []
    by_bucket: Counter[str] = Counter()
    by_task: Counter[str] = Counter()
    by_signal: Counter[str] = Counter()
    queue_counts: Counter[str] = Counter()
    missing_rows: list[str] = []

    for miss in misses:
        row_id = str(miss.get("row_id") or "")
        row = rows.get(row_id)
        if row is None:
            missing_rows.append(row_id)
            continue
        task = task_from_row(row)
        bucket = repo_bucket(row)
        missing_signal, flags, recommended_action = classify_missing_signal(row, miss)
        by_bucket[bucket] += 1
        by_task[task] += 1
        by_signal[missing_signal] += 1
        queue_counts[recommended_action] += 1

        target_label = str(miss.get("target"))
        predicted_label = str(miss.get("predicted"))
        card = {
            "row_id": row_id,
            "root_id": row.get("root_id"),
            "root_lineage_key": row.get("root_lineage_key"),
            "repo_family": row.get("repo_family"),
            "repo_bucket": bucket,
            "task_type": task,
            "target_label": target_label,
            "predicted_label": predicted_label,
            "full_vocab_top1_text": miss.get("full_vocab_top1_text"),
            "target_rank_full_vocab": miss.get("target_rank_full_vocab"),
            "gemma12b_correct_on_same_row": row_id not in gemma_miss_ids,
            "semantic_target_value": row.get("semantic_target_value"),
            "target_option": compact_option(option_by_label(row, target_label)),
            "predicted_option": compact_option(option_by_label(row, predicted_label)),
            "options": [compact_option(option) for option in options_for(row)],
            "prompt_preview": prompt_preview(row),
            "missing_signal_class": missing_signal,
            "flags": flags,
            "recommended_materialization_action": recommended_action,
            "admission_requirements": [
                "root-disjoint from heldout and protected canaries",
                "deterministic opaque option shuffle declared",
                "no gold semantic value visible before options",
                "selected test or verifier transition anchor present",
                "candidate_change_surface, verifier/test constraint, symptom/call-path, and insufficiency alternatives represented when task-appropriate",
            ],
        }
        cards.append(card)

    queue_items: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        grouped[card["recommended_materialization_action"]].append(card)
    for action, group in sorted(grouped.items()):
        queue_items.append(
            {
                "action": action,
                "miss_rows": len(group),
                "repo_buckets": dict(Counter(str(c["repo_bucket"]) for c in group)),
                "task_types": dict(Counter(str(c["task_type"]) for c in group)),
                "source_miss_row_ids": [str(c["row_id"]) for c in group],
                "minimum_next_supply": {
                    "train_roots": 10 if "llama_stack" in action or "openhands" in action else 5,
                    "heldout_roots": 3 if "llama_stack" in action or "openhands" in action else 2,
                    "repo_families": 2 if "openhands" in action else 1,
                },
                "do_not_train_on_source_misses": True,
            }
        )

    decision = "materialize_fresh_web_roots_before_training"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": decision,
        "selected_frontier": SELECTED_FRONTIER,
        "current_web_policy": CURRENT_WEB_POLICY,
        "source_metrics": {
            "stage11571_web_correct": web_result.get("correct"),
            "stage11571_web_rows": web_result.get("rows"),
            "stage11571_web_accuracy": web_result.get("accuracy"),
            "stage11549_gemma_correct": stage11549.get("gemma12b", {}).get("correct"),
            "stage11549_gemma_rows": stage11549.get("gemma12b", {}).get("rows"),
            "stage11549_gemma_accuracy": stage11549.get("gemma12b", {}).get("accuracy"),
        },
        "miss_summary": {
            "remaining_misses": len(cards),
            "missing_row_records": missing_rows,
            "by_repo_bucket": dict(by_bucket),
            "by_task_type": dict(by_task),
            "by_missing_signal_class": dict(by_signal),
            "by_recommended_action": dict(queue_counts),
            "gemma_correct_on_100m_misses": sum(1 for card in cards if card["gemma12b_correct_on_same_row"]),
        },
        "outputs": {
            "audit_dir": rel(OUT),
            "miss_cards": rel(OUT / "remaining_web_miss_cards.jsonl"),
            "materialization_queue": rel(OUT / "web_materialization_queue.jsonl"),
            "summary": rel(SUMMARY),
        },
        "source_artifacts": {
            "web_rows": rel(WEB_ROWS),
            "stage11571": rel(STAGE11571),
            "stage11549": rel(STAGE11549),
        },
        "claim_boundary": [
            "This is a deterministic materialization audit, not a new model score.",
            "No GPU inference or training is performed.",
            "The selected frontier remains stage11507 unless a later run improves Web heldout or residual gates without preservation regression.",
        ],
    }

    write_jsonl(OUT / "remaining_web_miss_cards.jsonl", cards)
    write_jsonl(OUT / "web_materialization_queue.jsonl", queue_items)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": decision,
        "misses": summary["miss_summary"],
        "queue_items": len(queue_items),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
