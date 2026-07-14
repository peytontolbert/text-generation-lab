#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10417
NAME = "stage10417_multilingual_reviewed_scaling_atlas"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "multilingual_reviewed_scaling_atlas.json"

REVIEW_ROOTS = [
    ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets",
    ROOT / "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets",
    ROOT / "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/review_packets",
    ROOT / "runs/local/artifacts/stage10415_rust_flash_attn_review_packets/review_packets",
]
SUCCESSOR_SALVAGE_PATH = ROOT / "runs/local/artifacts/stage10410_ai_adjudicated_successor_salvage/ai_adjudicated_successor_salvage.json"
REVIEW_BLOCKED_INVENTORY_PATH = ROOT / "runs/local/artifacts/stage10409_review_blocked_successor_inventory/review_blocked_successor_inventory.json"
DATASET_SCALE_AUDIT_PATH = ROOT / "runs/local/artifacts/stage10412_multilingual_dataset_scale_audit/multilingual_dataset_scale_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _read_bundle_packet(packet_dir: Path) -> dict[str, Any] | None:
    rubric_path = packet_dir / "expert_maintainer_rubric_review.json"
    anti_cheat_path = packet_dir / "anti_cheat_review_card.json"
    gold_path = packet_dir / "perspective_gold_adjudication.json"
    if not (rubric_path.exists() and anti_cheat_path.exists() and gold_path.exists()):
        return None

    rubric = load_json(rubric_path)
    anti_cheat = load_json(anti_cheat_path)
    gold = load_json(gold_path)
    answers = gold.get("perspective_gold_answers") if isinstance(gold.get("perspective_gold_answers"), list) else []

    selected_tests = sorted(
        {
            selected_test
            for answer in answers
            for selected_test in (answer.get("selected_tests") or [])
            if selected_test
        }
    )
    candidate_paths = []
    if answers:
        candidate_paths = list(answers[0].get("candidate_paths") or [])

    abstention_count = sum(1 for answer in answers if answer.get("gold_answer_kind") == "abstain")
    non_abstention_count = sum(1 for answer in answers if answer.get("gold_answer_kind") not in (None, "", "abstain"))
    visible_evidence_keys = []
    if answers:
        visible_evidence_keys = list(answers[0].get("visible_evidence_keys") or [])

    admitted = (
        rubric.get("bundle_valid_for_eval") is True
        and anti_cheat.get("admissible_for_same_surface_comparison") is True
        and gold.get("bundle_gold_ready_for_eval") is True
        and rubric.get("status") == "completed"
        and anti_cheat.get("status") == "completed"
        and gold.get("status") == "completed"
    )

    return {
        "bundle_id": gold.get("bundle_id") or rubric.get("bundle_id") or anti_cheat.get("bundle_id"),
        "language_family": gold.get("language_family") or rubric.get("language_family") or anti_cheat.get("language_family"),
        "repo_id": gold.get("repo_id") or rubric.get("repo_id") or anti_cheat.get("repo_id"),
        "packet_dir": rel(packet_dir),
        "bundle_valid_for_eval": bool(rubric.get("bundle_valid_for_eval") is True),
        "admissible_for_same_surface_comparison": bool(anti_cheat.get("admissible_for_same_surface_comparison") is True),
        "bundle_gold_ready_for_eval": bool(gold.get("bundle_gold_ready_for_eval") is True),
        "admitted": admitted,
        "selected_tests_count": len(selected_tests),
        "selected_tests": selected_tests,
        "candidate_paths_count": len(candidate_paths),
        "candidate_paths": candidate_paths,
        "visible_evidence_key_count": len(visible_evidence_keys),
        "visible_evidence_keys": visible_evidence_keys,
        "abstention_count": abstention_count,
        "non_abstention_count": non_abstention_count,
        "gold_answer_count": len(answers),
        "decision_rationale": gold.get("decision_rationale") or rubric.get("decision_rationale") or anti_cheat.get("decision_rationale"),
        "reviewer_id": gold.get("reviewer_id") or rubric.get("reviewer_id") or anti_cheat.get("reviewer_id"),
    }


def collect_reviewed_bundles() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for review_root in REVIEW_ROOTS:
        if not review_root.exists():
            continue
        for packet_dir in sorted(path for path in review_root.iterdir() if path.is_dir()):
            row = _read_bundle_packet(packet_dir)
            if row is not None:
                rows.append(row)
    return rows


def main() -> None:
    bundles = collect_reviewed_bundles()
    successor_salvage = load_json(SUCCESSOR_SALVAGE_PATH)
    review_blocked_inventory = load_json(REVIEW_BLOCKED_INVENTORY_PATH)
    dataset_scale_audit = load_json(DATASET_SCALE_AUDIT_PATH)

    admitted_bundles = [row for row in bundles if row["admitted"]]
    blocked_bundles = [row for row in bundles if not row["admitted"]]

    admitted_bundle_language_counts = Counter(row["language_family"] for row in admitted_bundles)
    admitted_bundle_repo_counts = Counter(f'{row["language_family"]}::{row["repo_id"]}' for row in admitted_bundles)
    verifier_anchored_language_counts = Counter(
        row["language_family"] for row in admitted_bundles if row["selected_tests_count"] > 0
    )
    abstention_heavy_language_counts = Counter(
        row["language_family"] for row in admitted_bundles if row["abstention_count"] >= 4
    )

    successor_rows = successor_salvage.get("targeted_admitted_rows") if isinstance(successor_salvage.get("targeted_admitted_rows"), list) else []
    successor_language_counts = Counter(row["language_family"] for row in successor_rows)

    combined_scaling_counts = defaultdict(lambda: {"admitted_bundles": 0, "admitted_successor_rows": 0})
    for language, count in admitted_bundle_language_counts.items():
        combined_scaling_counts[language]["admitted_bundles"] = count
    for language, count in successor_language_counts.items():
        combined_scaling_counts[language]["admitted_successor_rows"] = count

    anti_cheat_risks = []
    for row in admitted_bundles:
        risk_flags = []
        if row["selected_tests_count"] == 0:
            risk_flags.append("no_selected_test_anchor")
        if row["candidate_paths_count"] <= 2:
            risk_flags.append("small_candidate_set")
        if row["abstention_count"] == row["gold_answer_count"]:
            risk_flags.append("all_rows_abstain")
        if row["abstention_count"] >= 4:
            risk_flags.append("abstention_heavy")
        if risk_flags:
            anti_cheat_risks.append(
                {
                    "bundle_id": row["bundle_id"],
                    "language_family": row["language_family"],
                    "repo_id": row["repo_id"],
                    "risk_flags": risk_flags,
                    "packet_dir": row["packet_dir"],
                }
            )

    next_priorities = []
    blocked_counts = review_blocked_inventory.get("review_blocked_non_frontier_counts") or {}
    for language in ("python", "c_cpp", "web_js_ts_html"):
        blocked_count = int(blocked_counts.get(language, 0) or 0)
        if blocked_count > 0:
            next_priorities.append(
                f"Convert {blocked_count} remaining review-blocked {language} successor rows into honest abstention or singleton support only where prompt-visible evidence justifies it."
            )
    if admitted_bundle_language_counts.get("rust", 0) < 3:
        next_priorities.append("Increase reviewed Rust bundle count beyond the current admitted set so Rust scaling is not carried by too few roots.")
    next_priorities.append("Prefer bundles with selected-test anchors and nontrivial candidate competition over additional bounded-choice permutations.")
    next_priorities.append("Track margin and verifier-anchor coverage alongside accuracy before promoting any v2.7 multilingual claim.")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "frontier_context": dataset_scale_audit.get("frontier_status"),
        "reviewed_bundle_metrics": {
            "reviewed_bundle_count": len(bundles),
            "admitted_bundle_count": len(admitted_bundles),
            "blocked_bundle_count": len(blocked_bundles),
            "admitted_bundle_language_counts": dict(sorted(admitted_bundle_language_counts.items())),
            "admitted_bundle_repo_counts": dict(sorted(admitted_bundle_repo_counts.items())),
            "verifier_anchored_admitted_language_counts": dict(sorted(verifier_anchored_language_counts.items())),
            "abstention_heavy_admitted_language_counts": dict(sorted(abstention_heavy_language_counts.items())),
        },
        "successor_support_metrics": {
            "admitted_successor_row_count": len(successor_rows),
            "admitted_successor_language_counts": dict(sorted(successor_language_counts.items())),
        },
        "combined_multilingual_scaling_inventory": {
            language: counts for language, counts in sorted(combined_scaling_counts.items())
        },
        "admitted_bundle_rows": admitted_bundles,
        "blocked_bundle_rows": blocked_bundles,
        "anti_cheat_risk_watchlist": anti_cheat_risks,
        "claim_boundary": [
            "This atlas measures reviewed multilingual scaling capacity, not model accuracy.",
            "An admitted bundle here is stronger evidence than a raw candidate row, but abstention-heavy packets still should not be overclaimed as unique repair localization wins.",
            "The current 47-row frontier remains small; this atlas only clarifies how much reviewed multilingual support exists to scale v2.7 honestly."
        ],
        "next_dataset_scaling_priorities": next_priorities,
        "next_best_step": (
            "Use the admitted reviewed bundles plus admitted successor rows to assemble a broader honest v2.7 support inventory, "
            "then prioritize fresh Python/C++/pure-web roots and verifier-anchored anti-cheat audits before another promotion run."
        ),
    }
    write_json(SUMMARY_PATH, summary)


if __name__ == "__main__":
    main()
