#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10740
NAME = "stage10740_cpp_bulk_materialization_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "cpp_bulk_materialization_queue.json"
QUEUE_JSONL = OUT_DIR / "cpp_bulk_materialization_queue.jsonl"
REVIEWED_JSONL = OUT_DIR / "cpp_reviewed_train_support_roots.jsonl"
BOOTSTRAP_JSONL = OUT_DIR / "cpp_clean_bootstrap_candidates.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SCALE_PACKAGE = ROOT / "runs/local/artifacts/stage10739_multilingual_root_scale_package_v2/multilingual_root_scale_package_v2.json"
SCALE_INVENTORY = ROOT / "runs/local/artifacts/stage10739_multilingual_root_scale_package_v2/scale_ready_root_inventory.jsonl"
ADMISSION_V3 = ROOT / "runs/local/artifacts/stage10738_root_admission_manifest_v3/root_admission_manifest_v3.jsonl"
CPP_PACKET = ROOT / "runs/local/artifacts/stage10731_cpp_materialization_candidate_packet/cpp_materialization_candidate_packet.json"
CPP_SELECTED = ROOT / "runs/local/artifacts/stage10731_cpp_materialization_candidate_packet/cpp_materialization_selected_roots.jsonl"
CPP_REVIEWED = ROOT / "runs/local/artifacts/stage10734_cpp_ai_adjudicated_admission/cpp_ai_adjudicated_root_manifest.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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


def reviewed_queue_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "queue_role": "reviewed_train_support_root",
        "priority_band": "ready_now",
        "root_id": row["root_id"],
        "bundle_id": row.get("bundle_id") or row.get("root_id"),
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_family"),
        "language_family": "c_cpp",
        "quality_score_hint": float(row.get("quality_score_hint") or row.get("quality_score") or 0.91),
        "selected_test_anchor": bool(row.get("selected_test_anchor")),
        "verifier_anchor": bool(row.get("verifier_anchor")),
        "candidate_paths_count": int(row.get("candidate_paths_count") or 0),
        "task_type_count": int(row.get("task_type_count") or 0),
        "train_support_only": bool(row.get("train_support_only") if "train_support_only" in row else str(row.get("admit_role") or "") == "train"),
        "strict_eval_eligible": bool(row.get("strict_eval_eligible") if "strict_eval_eligible" in row else str(row.get("admit_role") or "") == "strict_eval"),
        "same_surface_eval_admissible": bool(row.get("same_surface_eval_admissible") or False),
        "packet_dir": row.get("packet_dir"),
        "rubric_review": row.get("rubric_review"),
        "anti_cheat_review": row.get("anti_cheat_review"),
        "perspective_gold_adjudication": row.get("perspective_gold_adjudication"),
        "recommended_next_action": "reuse_as_reviewed_train_support_and_template_for_bootstrap_materialization",
        "claim_boundary": row.get("claim_notes") or row.get("notes") or [],
    }


def bootstrap_queue_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "queue_role": "clean_bootstrap_materialization_candidate",
        "priority_band": "materialize_next",
        "root_id": row["root_id"],
        "bundle_id": None,
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_family"),
        "language_family": "c_cpp",
        "quality_score_hint": 0.48,
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "candidate_paths_count": 0,
        "task_type_count": 4,
        "train_support_only": False,
        "strict_eval_eligible": False,
        "same_surface_eval_admissible": False,
        "source_snapshot_id": row.get("snapshot_id"),
        "source_split_component": row.get("split_component"),
        "target_richness_score": int(row.get("target_richness_score") or 0),
        "target_subtypes": row.get("target_subtypes") or {},
        "target_families": row.get("target_families") or {},
        "recommended_next_action": "materialize_into_stage10733_style_review_packet_then_admit_train_support_only",
        "claim_boundary": [
            "clean_bootstrap_candidate",
            "root_lineage_not_yet_reviewed",
            "do_not_promote_to_strict_until_review_and_anti_cheat_complete",
        ],
    }


def main() -> None:
    scale_package = load_json(SCALE_PACKAGE)
    load_jsonl(SCALE_INVENTORY)
    admission_rows = load_jsonl(ADMISSION_V3)
    cpp_packet = load_json(CPP_PACKET)
    cpp_selected = load_jsonl(CPP_SELECTED)
    cpp_reviewed = load_jsonl(CPP_REVIEWED)

    cpp_reviewed_ids = {str(row.get("root_id") or "") for row in cpp_reviewed}
    reviewed_rows = list(cpp_reviewed)
    for row in admission_rows:
        if str(row.get("language_family") or "") != "c_cpp":
            continue
        if str(row.get("source_kind") or "") != "reviewed_bundle_root":
            continue
        if str(row.get("admit_role") or "") != "train":
            continue
        root_id = str(row.get("root_id") or "")
        if root_id in cpp_reviewed_ids:
            continue
        reviewed_rows.append(
            {
                "root_id": root_id,
                "bundle_id": root_id,
                "repo_id": row.get("repo_id"),
                "repo_family": row.get("repo_family"),
                "selected_test_anchor": row.get("selected_test_anchor"),
                "verifier_anchor": row.get("verifier_anchor"),
                "train_support_only": True,
                "strict_eval_eligible": False,
                "same_surface_eval_admissible": False,
                "claim_notes": row.get("notes") or [],
                "quality_score": row.get("quality_score"),
            }
        )
    reviewed_rows = sorted(reviewed_rows, key=lambda row: (str(row.get("repo_family") or ""), str(row.get("root_id") or "")))
    bootstrap_rows = sorted(cpp_selected, key=lambda row: (str(row.get("repo_family") or ""), str(row.get("root_id") or "")))

    queue_rows = [reviewed_queue_row(row) for row in reviewed_rows] + [bootstrap_queue_row(row) for row in bootstrap_rows]
    queue_rows.sort(
        key=lambda row: (
            0 if row["queue_role"] == "reviewed_train_support_root" else 1,
            str(row.get("repo_family") or ""),
            str(row.get("root_id") or ""),
        )
    )

    repo_family_counts = Counter(str(row.get("repo_family") or "unknown") for row in queue_rows)
    role_counts = Counter(str(row.get("queue_role") or "unknown") for row in queue_rows)
    per_role_repo_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for role in role_counts:
        counts = Counter(str(row.get("repo_family") or "unknown") for row in queue_rows if str(row.get("queue_role") or "") == role)
        per_role_repo_counts[role] = dict(sorted(counts.items()))

    c_cpp_lane = next(card for card in load_jsonl(OUT_DIR.parent / "stage10739_multilingual_root_scale_package_v2" / "language_scale_cards.jsonl") if card["language_family"] == "c_cpp")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "cpp_bulk_materialization_queue_ready",
        "claim_scope": [
            "Unify the current C/C++ reviewed train-support roots and the clean bootstrap materialization candidates into one concrete expansion queue.",
            "Make the next C/C++ scaling sprint executable from a single artifact instead of splitting context across stage10731, stage10734, and stage10739.",
            "Keep strict-claim boundaries explicit: this queue is for reviewed train-support and bundle materialization, not new strict headline rows.",
        ],
        "headline_findings": [
            f"C/C++ now has {len(reviewed_rows)} admitted reviewed train-support roots plus {len(bootstrap_rows)} clean bootstrap roots ready for materialization.",
            "The next honest C/C++ scale move is not another probe; it is turning the 5 clean bootstrap roots into stage10733-style reviewed packets.",
            "This queue keeps repo-family diversity explicit so expansion does not collapse into parametergolf-only faux scale.",
        ],
        "lane_context": {
            "strict_accuracy": c_cpp_lane["strict_accuracy"],
            "lane_blocker": c_cpp_lane["lane_blocker"],
            "phase_1_gap": c_cpp_lane["gaps"]["phase_1"],
            "reviewed_bundle_roots_current": (scale_package.get("global_counts") or {}).get("reviewed_bundle_roots_by_language_current", {}).get("c_cpp"),
            "ready_for_large_scale_train_current": (scale_package.get("global_counts") or {}).get("ready_for_large_scale_train_by_language", {}).get("c_cpp"),
        },
        "queue_metrics": {
            "total_queue_roots": len(queue_rows),
            "reviewed_train_support_roots": len(reviewed_rows),
            "clean_bootstrap_materialization_roots": len(bootstrap_rows),
            "repo_family_counts": dict(sorted(repo_family_counts.items())),
            "role_counts": dict(sorted(role_counts.items())),
            "per_role_repo_family_counts": per_role_repo_counts,
            "bootstrap_target_richness_scores": [int(row.get("target_richness_score") or 0) for row in bootstrap_rows],
            "all_bootstrap_candidates_leak_clean": all(int(row.get("prompt_target_leak_rows") or 0) == 0 for row in bootstrap_rows),
        },
        "anti_cheat_contract": [
            "Do not upgrade any queue entry to strict eval without bundle review, anti-cheat signoff, and explicit source-heldout admission.",
            "Bootstrap candidates must be materialized into maintainer-visible packets before any train/eval use beyond inventory accounting.",
            "Keep repo-family caps visible during expansion so repeated parametergolf roots do not masquerade as breadth.",
            "Preserve root-lineage disjointness between reviewed roots, bootstrap candidates, and any future strict-heldout C/C++ packets.",
        ],
        "next_best_steps": [
            "Materialize the 5 clean bootstrap C/C++ roots into stage10733-style review packets.",
            "Admit those new packets through the same AI-adjudicated bundle-admission path used in stage10734.",
            "Only after that, merge them into the reviewed train-support package and rerun a same-manifest probe.",
        ],
        "source_artifacts": {
            "scale_package_v2": display(SCALE_PACKAGE),
            "cpp_materialization_candidate_packet": display(CPP_PACKET),
            "cpp_materialization_selected_roots": display(CPP_SELECTED),
            "cpp_ai_adjudicated_root_manifest": display(CPP_REVIEWED),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "queue_jsonl": display(QUEUE_JSONL),
            "reviewed_roots_jsonl": display(REVIEWED_JSONL),
            "bootstrap_roots_jsonl": display(BOOTSTRAP_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(QUEUE_JSONL, queue_rows)
    write_jsonl(REVIEWED_JSONL, [reviewed_queue_row(row) for row in reviewed_rows])
    write_jsonl(BOOTSTRAP_JSONL, [bootstrap_queue_row(row) for row in bootstrap_rows])
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "summary_json": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
