from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10409_review_blocked_successor_inventory"
STAGE10110_PATH = ROOT / "runs/local/artifacts/stage10110_real_session_shortcut_safe_successor_packet/real_session_shortcut_safe_successor_packet.jsonl"
STAGE10114_PATH = ROOT / "runs/local/artifacts/stage10114_real_session_successor_review_priority_atlas/real_session_successor_review_priority_queue.jsonl"
STAGE10120_DIR = ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets"
STAGE10127_DIR = ROOT / "runs/local/artifacts/stage10127_true_source_backed_rust_root_bundle_review_packets/review_packets"


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open() as handle:
        for line in handle:
            rows.append(json.loads(line))
    return rows


def current_frontier_episode_ids() -> set[str]:
    episode_ids: set[str] = set()
    for base in (STAGE10120_DIR, STAGE10127_DIR):
        if not base.is_dir():
            continue
        for packet_dir in sorted(base.iterdir()):
            name = packet_dir.name
            if not name.startswith("stage10119__"):
                continue
            stem = name[len("stage10119__") :]
            episode_id, _, _language = stem.rpartition("__")
            if episode_id:
                episode_ids.add(episode_id)
    return episode_ids


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    stage10110_rows = load_jsonl(STAGE10110_PATH)
    stage10114_rows = load_jsonl(STAGE10114_PATH)
    queue_by_row_id = {row["row_id"]: row for row in stage10114_rows}
    frontier_episodes = current_frontier_episode_ids()

    inventory_rows: list[dict] = []
    overlap_counts = Counter()
    reusable_counts = Counter()
    reusable_repo_counts = Counter()
    reusable_template_counts = Counter()
    reusable_priority_counts = Counter()
    reusable_shortcut_counts = Counter()

    for row in stage10110_rows:
        row_id = row["row_id"]
        queue_row = queue_by_row_id.get(row_id, {})
        episode_id = row["episode_id"]
        overlaps_frontier = episode_id in frontier_episodes

        record = {
            "row_id": row_id,
            "episode_id": episode_id,
            "language_family": row["language_family"],
            "repo_id": row.get("repo_id"),
            "successor_template": row.get("successor_template"),
            "candidate_count": len(row.get("prompt_surface", {}).get("candidate_choices", [])),
            "visible_evidence_count": len(row.get("prompt_surface", {}).get("visible_evidence", [])),
            "selected_tests_count": len(row.get("hidden_metadata", {}).get("selected_tests", [])),
            "current_frontier_overlap": overlaps_frontier,
            "review_blocked": True,
            "review_priority_rank": queue_row.get("review_priority_rank"),
            "priority_tier": queue_row.get("priority_tier"),
            "priority_score": queue_row.get("priority_score"),
            "candidate_surface_pair": queue_row.get("candidate_surface_pair"),
            "shortcut_risk_score": queue_row.get("shortcut_risk_score"),
            "shortcut_risk_reasons": queue_row.get("shortcut_risk_reasons", []),
            "claim_criticality_score": queue_row.get("claim_criticality_score"),
            "claim_criticality_reasons": queue_row.get("claim_criticality_reasons", []),
            "recommendation": (
                "keep_in_current_frontier_only"
                if overlaps_frontier
                else "candidate_for_ai_adjudication_salvage"
            ),
        }
        inventory_rows.append(record)

        if overlaps_frontier:
            overlap_counts[row["language_family"]] += 1
        else:
            reusable_counts[row["language_family"]] += 1
            reusable_repo_counts[(row["language_family"], row.get("repo_id"))] += 1
            reusable_template_counts[(row["language_family"], row.get("successor_template"))] += 1
            reusable_priority_counts[(row["language_family"], queue_row.get("priority_tier", "unknown"))] += 1
            reusable_shortcut_counts[(row["language_family"], queue_row.get("shortcut_risk_score", -1))] += 1

    reusable_candidates = [row for row in inventory_rows if not row["current_frontier_overlap"]]
    reusable_candidates.sort(
        key=lambda row: (
            row["language_family"],
            -(row["priority_score"] or -1),
            row["shortcut_risk_score"] if row["shortcut_risk_score"] is not None else 999,
            row["row_id"],
        )
    )

    shortlist: dict[str, list[dict]] = defaultdict(list)
    for row in sorted(
        reusable_candidates,
        key=lambda item: (
            item["language_family"],
            item["shortcut_risk_score"] if item["shortcut_risk_score"] is not None else 999,
            -(item["selected_tests_count"] or 0),
            -(item["priority_score"] or 0),
            item["row_id"],
        ),
    ):
        if row["language_family"] == "rust":
            continue
        if len(shortlist[row["language_family"]]) >= 3:
            continue
        shortlist[row["language_family"]].append(
            {
                "row_id": row["row_id"],
                "repo_id": row["repo_id"],
                "successor_template": row["successor_template"],
                "priority_tier": row["priority_tier"],
                "priority_score": row["priority_score"],
                "shortcut_risk_score": row["shortcut_risk_score"],
                "selected_tests_count": row["selected_tests_count"],
                "candidate_surface_pair": row["candidate_surface_pair"],
            }
        )

    language_examples: dict[str, list[dict]] = defaultdict(list)
    for row in reusable_candidates:
        bucket = language_examples[row["language_family"]]
        if len(bucket) >= 5:
            continue
        bucket.append(
            {
                "row_id": row["row_id"],
                "repo_id": row["repo_id"],
                "successor_template": row["successor_template"],
                "priority_tier": row["priority_tier"],
                "priority_score": row["priority_score"],
                "shortcut_risk_score": row["shortcut_risk_score"],
                "selected_tests_count": row["selected_tests_count"],
            }
        )

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stage": 10409,
        "stage_name": "stage10409_review_blocked_successor_inventory",
        "claim_boundary": [
            "These rows are not admitted. They remain blocked on rubric, anti-cheat, and gold adjudication.",
            "This inventory corrects the narrower stage10408 claim by separating missing reviewed roots from missing raw source candidates.",
        ],
        "source_artifacts": {
            "stage10110_packet": str(STAGE10110_PATH.relative_to(ROOT)),
            "stage10114_priority_queue": str(STAGE10114_PATH.relative_to(ROOT)),
        },
        "frontier_overlap_counts": dict(overlap_counts),
        "review_blocked_non_frontier_counts": dict(reusable_counts),
        "review_blocked_non_frontier_repo_counts": {
            f"{language}::{repo}": count for (language, repo), count in sorted(reusable_repo_counts.items())
        },
        "review_blocked_non_frontier_template_counts": {
            f"{language}::{template}": count
            for (language, template), count in sorted(reusable_template_counts.items())
        },
        "review_blocked_non_frontier_priority_counts": {
            f"{language}::{tier}": count for (language, tier), count in sorted(reusable_priority_counts.items())
        },
        "language_examples": language_examples,
        "ai_adjudication_shortlist": shortlist,
        "implications": [
            "Python and C/C++ do have additional real-session source candidates beyond the admitted frontier, but they are review-blocked and many remain shortcut-sensitive.",
            "Web has one extra non-frontier successor row from code_assist, but that still does not replace the need for a pure second web maintainer root if the claim requires it.",
            "Rust still has no additional candidates in this successor packet; a new Rust root builder remains necessary.",
        ],
    }

    (ARTIFACT_DIR / "review_blocked_successor_inventory.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (ARTIFACT_DIR / "review_blocked_successor_inventory_rows.jsonl").open("w") as handle:
        for row in reusable_candidates:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
