#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
NAME = "stage11515_selected_frontier_anticheat_claim_audit"
OUT_DIR = ART / NAME
OUT_JSON = SUM / f"{NAME}.json"

PAYLOAD = ART / "stage11511_selected_frontier_harness_payload/selected_frontier_harness_payload.json"
RUNTIME = ART / "stage11512_selected_frontier_harness_local_runtime/canonical_harness_local_runtime_summary.json"
WRITEBACK = ART / "stage11513_selected_frontier_harness_writeback/reviewed_v28_harness_writeback_repair.json"
HARNESS_AUDIT = SUM / "stage11514_selected_frontier_harness_result_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def before_options(prompt: str) -> str:
    marker = "\nOptions:"
    return prompt.split(marker, 1)[0] if marker in prompt else prompt


def extract_rows(payload: MappingLike) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in payload.get("runs") or []:
        task_pack = run.get("task_pack") or {}
        for row in task_pack.get("manifest_rows") or []:
            item = dict(row)
            item["_cell_key"] = run.get("cell_key")
            item["_task_pack_id"] = task_pack.get("task_pack_id")
            item["_train_eligible"] = task_pack.get("train_eligible")
            item["_blocked_training_reason"] = task_pack.get("blocked_training_reason")
            rows.append(item)
    return rows


MappingLike = dict[str, Any]


def main() -> None:
    payload = load_json(PAYLOAD)
    runtime = load_json(RUNTIME)
    writeback = load_json(WRITEBACK)
    harness_audit = load_json(HARNESS_AUDIT)
    rows = extract_rows(payload)

    failures: list[str] = []
    risk_flags: list[str] = []

    if harness_audit.get("passed") is not True:
        failures.append("stage11514_harness_audit_not_passed")
    if runtime.get("passed") is not True:
        failures.append("stage11512_runtime_not_passed")
    if writeback.get("passed") is not True:
        failures.append("stage11513_writeback_not_passed")
    if not rows:
        failures.append("no_manifest_rows")

    label_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    option_count_distribution: Counter[int] = Counter()
    root_counts: Counter[str] = Counter()
    repo_counts: Counter[str] = Counter()
    anti_cheat_counts: Counter[str] = Counter()
    direct_value_before_options: list[dict[str, str]] = []
    singleton_rows: list[dict[str, str]] = []
    non_opaque_rows: list[str] = []
    train_eligible_rows: list[str] = []
    missing_required_fields: list[dict[str, Any]] = []

    required_row_fields = ("row_id", "language_family", "task_type", "opaque_options")
    for row in rows:
        row_id = str(row.get("row_id") or "")
        prompt = str(row.get("prompt") or row.get("prompt_text") or row.get("input_text") or "")
        label = str(row.get("expected_label") or row.get("decoder_text") or row.get("target_label") or row.get("target") or "")
        missing = [field for field in required_row_fields if row.get(field) in (None, "", [])]
        if not prompt:
            missing.append("prompt_or_prompt_text")
        if not label:
            missing.append("expected_label_or_decoder_text")
        if missing:
            missing_required_fields.append({"row_id": row_id, "missing": missing})

        label_counts[label] += 1
        language_counts[str(row.get("language_family") or "unknown")] += 1
        task_counts[str(row.get("task_type") or "unknown")] += 1
        root_counts[str(row.get("source_root_id") or row.get("source_bundle_id") or "unknown")] += 1
        repo_counts[str(row.get("repo_family") or row.get("repo_id") or "unknown")] += 1

        options = [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]
        option_count_distribution[len(options)] += 1
        if len(options) <= 1:
            singleton_rows.append({"row_id": row_id, "task_type": str(row.get("task_type") or ""), "language_family": str(row.get("language_family") or "")})

        if row.get("_train_eligible") is not False:
            train_eligible_rows.append(row_id)

        anti_cheat = row.get("anti_cheat") or {}
        if isinstance(anti_cheat, dict):
            for key, value in anti_cheat.items():
                if value is True:
                    anti_cheat_counts[f"{key}=true"] += 1
                elif value is False:
                    anti_cheat_counts[f"{key}=false"] += 1
        option_labels = [str(opt.get("label") or "") for opt in options]
        if label and label not in option_labels:
            non_opaque_rows.append(row_id)

        expected_value = ""
        for opt in options:
            if str(opt.get("label") or "") == label:
                expected_value = str(opt.get("value") or "")
                break
        prompt_prefix = normalize_text(before_options(prompt))
        if expected_value:
            value_norm = normalize_text(expected_value)
            if len(value_norm) >= 4 and value_norm in prompt_prefix:
                direct_value_before_options.append(
                    {
                        "row_id": row_id,
                        "task_type": str(row.get("task_type") or ""),
                        "language_family": str(row.get("language_family") or ""),
                        "expected_value": expected_value,
                    }
                )

    if missing_required_fields:
        failures.append(f"missing_required_row_fields::{len(missing_required_fields)}")
    if train_eligible_rows:
        failures.append(f"locked_harness_rows_marked_train_eligible::{len(train_eligible_rows)}")
    if non_opaque_rows:
        failures.append(f"non_opaque_answer_rows::{len(non_opaque_rows)}")

    if singleton_rows:
        risk_flags.append(f"singleton_option_rows_present::{len(singleton_rows)}")
    if anti_cheat_counts.get("deterministic_option_shuffle=false", 0):
        risk_flags.append(f"deterministic_option_shuffle_not_asserted::{anti_cheat_counts['deterministic_option_shuffle=false']}")
    if len(root_counts) < max(8, len(language_counts) * 2):
        risk_flags.append(f"low_root_breadth::{len(root_counts)}_roots_for_{len(rows)}_rows")
    if direct_value_before_options:
        risk_flags.append(f"gold_value_visible_before_options::{len(direct_value_before_options)}")
    if any(row.get("source_heldout_admissible") is False for row in rows):
        risk_flags.append("source_heldout_claim_not_supported_for_all_rows")
    if all((row.get("verifier_anchor") is not True) for row in rows):
        risk_flags.append("no_verifier_anchored_rows")

    runtime_results = [row for row in runtime.get("results") or [] if isinstance(row, dict)]
    no_patch_rows = sum(1 for row in runtime_results if ((row.get("patch_minimality_or_abstain_scores") or {}).get("summary") or {}).get("rows") == 0)
    no_verifier_rows = sum(1 for row in runtime_results if ((row.get("verifier_results") or {}).get("summary") or {}).get("rows") == 0)
    if no_patch_rows == len(runtime_results):
        risk_flags.append("harness_has_no_patch_rows")
    if no_verifier_rows == len(runtime_results):
        risk_flags.append("harness_has_no_executable_verifier_rows")

    majority_label, majority_count = ("", 0)
    if label_counts:
        majority_label, majority_count = label_counts.most_common(1)[0]

    audit = {
        "stage": 11515,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not failures,
        "decision": "selected_frontier_anticheat_claim_audit_passed_with_scope_risks" if not failures else "selected_frontier_anticheat_claim_audit_failed",
        "claim_boundary": [
            "Supported: selected Stage11507 compact maintainer-choice bounded scorer beats Gemma on the locked 23-row same-task-pack harness packet.",
            "Not supported: broad source-heldout software-maintenance intelligence, freeform generation, executable patch repair, or full-product verifier/patch scoring.",
            "Risk flags are not hard failures unless they contradict the compact same-task-pack claim; they define what must be fixed before a broader claim.",
        ],
        "metrics": {
            "rows": len(rows),
            "languages": dict(sorted(language_counts.items())),
            "task_types": dict(sorted(task_counts.items())),
            "unique_roots": len(root_counts),
            "unique_repo_families": len(repo_counts),
            "label_distribution": dict(sorted(label_counts.items())),
            "majority_label": majority_label,
            "majority_label_accuracy_ceiling": majority_count / len(rows) if rows else 0.0,
            "option_count_distribution": {str(key): value for key, value in sorted(option_count_distribution.items())},
            "anti_cheat_counts": dict(sorted(anti_cheat_counts.items())),
            "singleton_rows": len(singleton_rows),
            "gold_value_visible_before_options": len(direct_value_before_options),
            "runtime_completed_runs": (runtime.get("metrics") or {}).get("completed_runs"),
            "writeback_repaired_runs": (writeback.get("metrics") or {}).get("repaired_runs"),
        },
        "samples": {
            "singleton_rows": singleton_rows[:10],
            "gold_value_visible_before_options": direct_value_before_options[:10],
            "largest_root_clusters": root_counts.most_common(10),
            "largest_repo_clusters": repo_counts.most_common(10),
        },
        "failures": failures,
        "risk_flags": risk_flags,
        "source_artifacts": {
            "harness_payload": rel(PAYLOAD),
            "runtime_summary": rel(RUNTIME),
            "writeback": rel(WRITEBACK),
            "harness_result_audit": rel(HARNESS_AUDIT),
        },
        "next_best_step": "Use this packet as a locked compact harness/canary result. Broader v2.7 promotion should require root-broader, option-shuffled, source-heldout rows with executable verifier/patch evidence.",
    }
    write_json(OUT_DIR / f"{NAME}.json", audit)
    write_json(OUT_JSON, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
