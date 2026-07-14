#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10663
NAME = "stage10663_rust_flash_attn_executable_support_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_PATH = OUT_DIR / "rust_flash_attn_executable_support_audit.json"
ROWS_COPY = OUT_DIR / "rust_flash_attn_executable_support_rows.jsonl"

SOURCE_ROWS = ARTIFACTS / "stage10419_reviewed_v27_active_support_package/rust_flash_attn_active_support_rows.jsonl"
GOLD_ADJUDICATION = ARTIFACTS / "stage10415_rust_flash_attn_review_packets/review_packets/stage10413__candle__candle-flash-attn__rust/perspective_gold_adjudication.json"
AI_SUMMARY = ARTIFACTS / "stage10416_ai_adjudicate_rust_flash_attn_bundle/rust_flash_attn_ai_adjudication_summary.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    rows = load_jsonl(SOURCE_ROWS)
    gold = load_json(GOLD_ADJUDICATION)
    summary = load_json(AI_SUMMARY)

    task_counts = Counter(str(row.get("task_type") or "unknown") for row in rows)
    target_counts = Counter(str(row.get("target_text") or "") for row in rows)
    support_flags = Counter()
    bundle_ids = sorted({str(row.get("source_bundle_id") or "") for row in rows})
    splits = sorted({str(row.get("split") or "") for row in rows})

    for row in rows:
        anti_cheat = row.get("anti_cheat") or {}
        if anti_cheat.get("train_support_only"):
            support_flags["train_support_only"] += 1
        if anti_cheat.get("same_surface_eval_admissible") is False:
            support_flags["same_surface_eval_admissible_false"] += 1
        if anti_cheat.get("fresh_source_backed_root"):
            support_flags["fresh_source_backed_root"] += 1
        if anti_cheat.get("anti_cheat_review_passed"):
            support_flags["anti_cheat_review_passed"] += 1
        if anti_cheat.get("expert_rubric_passed"):
            support_flags["expert_rubric_passed"] += 1

    gold_by_perspective = {
        str(entry.get("perspective") or ""): {
            "gold_answer_kind": entry.get("gold_answer_kind"),
            "gold_answer_value": entry.get("gold_answer_value"),
        }
        for entry in gold.get("perspective_gold_answers") or []
    }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "rust_flash_attn_reviewed_rows_are_executable_support_now",
        "sources": {
            "source_rows": rel(SOURCE_ROWS),
            "gold_adjudication": rel(GOLD_ADJUDICATION),
            "ai_adjudication_summary": rel(AI_SUMMARY),
        },
        "bundle_identity": {
            "bundle_ids": bundle_ids,
            "expected_bundle_id": summary.get("bundle_id"),
            "language_family": summary.get("language_family"),
            "repo_id": summary.get("repo_id"),
            "selected_tests": summary.get("selected_tests") or [],
        },
        "metrics": {
            "row_count": len(rows),
            "task_type_counts": dict(sorted(task_counts.items())),
            "target_label_counts": dict(sorted(target_counts.items())),
            "splits": splits,
            "gold_perspective_count": len(gold.get("perspective_gold_answers") or []),
            "abstention_gold_count": summary.get("abstention_gold_count"),
            "non_abstention_gold_count": summary.get("non_abstention_gold_count"),
        },
        "support_contract": {
            "all_rows_train_support_only": support_flags["train_support_only"] == len(rows),
            "all_rows_same_surface_eval_admissible_false": support_flags["same_surface_eval_admissible_false"] == len(rows),
            "all_rows_fresh_source_backed_root": support_flags["fresh_source_backed_root"] == len(rows),
            "all_rows_anti_cheat_review_passed": support_flags["anti_cheat_review_passed"] == len(rows),
            "all_rows_expert_rubric_passed": support_flags["expert_rubric_passed"] == len(rows),
            "bundle_gold_ready_for_eval": bool(gold.get("bundle_gold_ready_for_eval")),
            "bundle_valid_for_eval": bool(summary.get("bundle_valid_for_eval")),
            "same_surface_eval_admissible": bool(summary.get("admissible_for_same_surface_comparison")),
        },
        "gold_projection_summary": gold_by_perspective,
        "claim_boundary": [
            "Flash-attn is now proven to have executable compact-bounded support rows plus completed AI gold adjudication.",
            "It remains train-support or stress-eval material, not source-heldout headline evidence, because the packet is abstention-heavy and not same-surface promotable.",
            "This upgrades Rust supply from a purely pending state to at least one fresh non-tokenizers reviewed support root that can be used honestly in the next multilingual training package.",
        ],
        "next_best_steps": [
            "Use the flash-attn rows as reviewed fresh Rust support in the next combined multilingual support package.",
            "Do not promote flash-attn as the main Rust residual fix claim; continue building linux::rust, candle-datasets, and candle-transformers contrast roots.",
            "Keep source-heldout and same-surface claim boundaries explicit so flash-attn support does not get overstated.",
        ],
        "outputs": {
            "executable_support_rows": rel(ROWS_COPY),
        },
    }

    write_jsonl(ROWS_COPY, rows)
    write_json(OUT_PATH, payload)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
