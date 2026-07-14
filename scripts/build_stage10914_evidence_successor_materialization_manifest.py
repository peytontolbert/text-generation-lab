#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10914
NAME = "stage10914_evidence_successor_materialization_manifest"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "evidence_successor_materialization_manifest.json"
OUT_JSONL = OUT_DIR / "candidate_rows.jsonl"

QUEUE_JSONL = ARTIFACTS / "stage10913_multilingual_evidence_root_build_queue" / "root_build_queue.jsonl"


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


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    queue_rows = load_jsonl(QUEUE_JSONL)
    candidate_rows: list[dict[str, Any]] = []

    for queue in queue_rows:
        status = str(queue.get("status") or "")
        if status != "ready_to_materialize":
            continue
        packet_dir = ROOT / str(queue["packet_dir"])
        gold = load_json(packet_dir / "perspective_gold_adjudication.json")
        anti_cheat = load_json(packet_dir / "anti_cheat_review_card.json")
        gold_rows = gold.get("perspective_gold_answers") or []
        evidence_gold = next(
            (row for row in gold_rows if str(row.get("perspective") or "") == "evidence_citation"),
            None,
        )
        if evidence_gold is None:
            continue

        gold_value = str(evidence_gold.get("gold_answer_value") or "")
        competition = "B_vs_F" if gold_value in {"verifier_and_test_constraint", "candidate_change_surface"} else "other"
        current_checked_target = str(queue.get("current_checked_target") or "")
        current_checked_target_value = {
            "B": "candidate_change_surface",
            "F": "verifier_and_test_constraint",
        }.get(current_checked_target, "")

        candidate_rows.append(
            {
                "stage": STAGE,
                "queue_id": queue["queue_id"],
                "language_family": queue["language_family"],
                "repo_id": queue["repo_id"],
                "source_bundle_id": queue["source_bundle_id"],
                "packet_dir": queue["packet_dir"],
                "materialization_mode": "fresh_source_backed_evidence_successor",
                "target_family": "evidence_citation",
                "competition_family": competition,
                "gold_answer_kind": str(evidence_gold.get("gold_answer_kind") or ""),
                "gold_answer_value": gold_value,
                "selected_tests": list(evidence_gold.get("selected_tests") or queue.get("selected_tests") or []),
                "candidate_paths": list(evidence_gold.get("candidate_paths") or queue.get("candidate_paths") or []),
                "visible_evidence_keys": list(evidence_gold.get("visible_evidence_keys") or []),
                "reviewer_rationale": str(evidence_gold.get("reviewer_rationale") or ""),
                "current_checked_row_id": queue.get("current_checked_row_id"),
                "current_checked_target_label": current_checked_target,
                "current_checked_target_value": current_checked_target_value,
                "current_checked_failure": queue.get("current_checked_failure"),
                "anti_cheat_challenge_families": sorted(
                    [key for key, value in (anti_cheat.get("challenge_families") or {}).items() if value]
                ),
                "anti_cheat_decision_rationale": anti_cheat.get("decision_rationale"),
                "materialization_requirements": [
                    "Preserve all six visible evidence keys in the candidate packet.",
                    "Keep candidate_change_surface plausible in visible evidence.",
                    "Make verifier_and_test_constraint uniquely justified when gold is F.",
                    "Do not expose target path strings before options.",
                    "Retain selected tests as visible verifier anchors.",
                ],
                "scoring_readiness": {
                    "anti_cheat_completed": anti_cheat.get("status") == "completed",
                    "gold_ready": bool(gold.get("bundle_gold_ready_for_eval")),
                    "same_surface_comparison_admissible": bool(anti_cheat.get("admissible_for_same_surface_comparison")),
                },
                "next_action": "materialize_fresh_candidate_rows",
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(candidate_rows),
        "claim_scope": [
            "Package the reviewed evidence gold answers and anti-cheat constraints into a direct materialization manifest for fresh Python and C/C++ evidence-citation successors.",
            "Avoid re-parsing review packets in the next stage by emitting row-builder inputs with explicit gold evidence keys, selected tests, candidate paths, and challenge-family constraints.",
        ],
        "source_queue": rel(QUEUE_JSONL),
        "candidate_count": len(candidate_rows),
        "languages": sorted({row["language_family"] for row in candidate_rows}),
        "findings": [
            "The repository_library Python packet and parametergolf C/C++ packet both have adjudicated evidence_citation gold = verifier_and_test_constraint, matching the current B-versus-F failure family.",
            "The agentkernel C/C++ packet remains useful as a counter-family because its evidence_citation gold is candidate_change_surface, making it the right positive control against over-correcting to F.",
            "All emitted candidates carry anti-cheat challenge families and selected-test anchors forward into the next materialization step.",
        ],
        "next_best_step": "Use candidate_rows.jsonl as the direct input to build fresh evidence successor rows for scoring or review, starting with Python repository_library and C/C++ parametergolf.",
        "outputs": {
            "manifest_json": rel(OUT_JSON),
            "candidate_rows_jsonl": rel(OUT_JSONL),
        },
    }

    write_json(OUT_JSON, payload)
    write_jsonl(OUT_JSONL, candidate_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
