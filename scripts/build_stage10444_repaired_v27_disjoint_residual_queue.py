#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10444
NAME = "stage10444_repaired_v27_disjoint_residual_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE_JSON = OUT_DIR / "repaired_v27_disjoint_residual_queue.json"
TARGETS_JSONL = OUT_DIR / "repaired_v27_disjoint_residual_targets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

REPAIRED_MARGIN_JSON = ROOT / "runs/local/artifacts/stage10438_repaired_v27_strict_overlay_saved_runtime_margin_audit/repaired_v27_strict_overlay_saved_runtime_margin_audit.json"
PYTHON_REQUEST_JSON = ROOT / "runs/local/artifacts/stage10439_python_verifier_disjoint_support_request/python_verifier_disjoint_support_request.json"
RUST_REQUEST_JSON = ROOT / "runs/local/artifacts/stage10441_rust_evidence_citation_fresh_builder_request/rust_evidence_citation_fresh_builder_request.json"
PYTHON_PROBE_JSON = ROOT / "runs/local/artifacts/stage10442_python_verifier_disjoint_support_probe/bounded_decoder_probe/execution_result.json"


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
    repaired_margin = load_json(REPAIRED_MARGIN_JSON)
    python_request = load_json(PYTHON_REQUEST_JSON)
    rust_request = load_json(RUST_REQUEST_JSON)
    python_probe = load_json(PYTHON_PROBE_JSON)

    probe_row_cards = python_probe["bounded_choice_eval"]["strict_eval"]["row_cards"]
    probe_by_row = {row["row_id"]: row for row in probe_row_cards}

    targets = []
    for row in repaired_margin["incorrect_rows"]:
        probe_row = probe_by_row[row["row_id"]]
        if row["language_family"] == "python":
            targets.append(
                {
                    "priority": 1,
                    "language_family": "python",
                    "task_type": row["task_type"],
                    "row_id": row["row_id"],
                    "residual_family": "verifier_target_disambiguation",
                    "baseline_predicted_label": row["predicted_label"],
                    "baseline_target_label": row["target_label"],
                    "baseline_top2_label": row["top2_label"],
                    "baseline_margin_top1_minus_top2": row["margin_top1_minus_top2"],
                    "probe_predicted_label": probe_row["constrained_choice_top1_label"],
                    "probe_target_label": probe_row["target_text"],
                    "probe_correct": probe_row["constrained_choice_match"],
                    "same_surface_replay_helped": probe_row["constrained_choice_match"],
                    "support_status": "fresh_disjoint_support_needed",
                    "required_support_shape": [
                        "new reviewed Python verifier_outcome roots with multiple plausible test-file candidates",
                        "selected-test anchor present but not directly answer-revealing",
                        "contrast between close sibling test targets, not generic verifier rows",
                        "no reuse of the current MirrorMind strict root in train support",
                    ],
                    "honesty_gates": python_request["required_honesty_gates"],
                    "promotion_boundary": "diagnostic_only_until_disjoint_roots_exist",
                }
            )
        else:
            targets.append(
                {
                    "priority": 2,
                    "language_family": "rust",
                    "task_type": row["task_type"],
                    "row_id": row["row_id"],
                    "residual_family": "evidence_support_disambiguation",
                    "baseline_predicted_label": row["predicted_label"],
                    "baseline_target_label": row["target_label"],
                    "baseline_top2_label": row["top2_label"],
                    "baseline_margin_top1_minus_top2": row["margin_top1_minus_top2"],
                    "probe_predicted_label": probe_row["constrained_choice_top1_label"],
                    "probe_target_label": probe_row["target_text"],
                    "probe_correct": probe_row["constrained_choice_match"],
                    "same_surface_replay_helped": probe_row["constrained_choice_match"],
                    "support_status": rust_request["current_residual_target"]["supply_status"],
                    "required_support_shape": rust_request["current_residual_target"]["required_support_shape"],
                    "builder_requirements": rust_request["builder_requirements"],
                    "recommended_candidates": [
                        item["candidate_root_id"] for item in rust_request["recommended_candidates"][:3]
                    ],
                    "promotion_boundary": "builder_then_review_then_strict_retest",
                }
            )

    targets.sort(key=lambda row: (row["priority"], row["language_family"], row["row_id"]))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Unified residual queue for the remaining repaired-v2.7 strict misses after the non-promotable stage10442 probe.",
            "This queue is for fresh disjoint support and builder work only; it must not be used to justify same-surface replay promotion.",
        ],
        "source_artifacts": {
            "repaired_overlay_margin_audit": display(REPAIRED_MARGIN_JSON),
            "python_residual_request": display(PYTHON_REQUEST_JSON),
            "rust_builder_request": display(RUST_REQUEST_JSON),
            "python_residual_probe": display(PYTHON_PROBE_JSON),
        },
        "summary": {
            "remaining_residuals": len(targets),
            "python_targets": sum(1 for row in targets if row["language_family"] == "python"),
            "rust_targets": sum(1 for row in targets if row["language_family"] == "rust"),
            "same_surface_replay_fixed_any": any(row["same_surface_replay_helped"] for row in targets),
        },
        "targets": targets,
        "recommended_stage_sequence": [
            "Build or admit fresh disjoint Python verifier roots first, because the current saved-runtime replay did not move the MirrorMind miss.",
            "Build or admit at least one fresh reviewed Rust evidence-citation root with a real candidate-surface-vs-support contrast.",
            "Re-test the frozen repaired overlay only after the new support roots are available and reviewed.",
        ],
        "outputs": {
            "queue_json": display(QUEUE_JSON),
            "targets_jsonl": display(TARGETS_JSONL),
        },
    }

    write_json(QUEUE_JSON, payload)
    write_jsonl(TARGETS_JSONL, targets)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
