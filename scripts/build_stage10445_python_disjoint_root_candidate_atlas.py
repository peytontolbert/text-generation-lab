#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10445
NAME = "stage10445_python_disjoint_root_candidate_atlas"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ATLAS_JSON = OUT_DIR / "python_disjoint_root_candidate_atlas.json"
ROWS_JSONL = OUT_DIR / "python_disjoint_root_candidate_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

CURRENT_RESIDUAL_QUEUE = ROOT / "runs/local/artifacts/stage10444_repaired_v27_disjoint_residual_queue/repaired_v27_disjoint_residual_queue.json"
REVIEW_PACKETS = ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets"
PYTHON_MIRRORMIND_BUNDLE = ROOT / "runs/local/artifacts/stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_bundle.json"
PYTHON_MIRRORMIND_EXACT_BUNDLE = ROOT / "runs/local/artifacts/stage10333_python_mirrormind_exact_geometry_execution_request/python_mirrormind_exact_geometry_bundle.json"
CODE_ASSIST_CONTEXT_BUNDLE = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/context_pack_python_replenishment_bundle.json"
CODE_ASSIST_HF_LOCAL_BUNDLE = ROOT / "runs/local/artifacts/stage10300_hf_local_python_replenishment_bundle/hf_local_python_replenishment_bundle.json"
SUCCESSOR_SALVAGE_JSON = ROOT / "runs/local/artifacts/stage10410_ai_adjudicated_successor_salvage/ai_adjudicated_successor_salvage.json"

FRONTIER_BUNDLE_IDS = {
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python",
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python",
}


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


def review_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet in sorted(REVIEW_PACKETS.iterdir()):
        if not packet.is_dir() or not packet.name.endswith("__python"):
            continue
        rubric = load_json(packet / "expert_maintainer_rubric_review.json")
        anti = load_json(packet / "anti_cheat_review_card.json")
        gold = load_json(packet / "perspective_gold_adjudication.json")
        bundle_id = str(rubric.get("bundle_id") or anti.get("bundle_id") or gold.get("bundle_id") or "")
        rows.append(
            {
                "candidate_root_id": bundle_id.replace("stage10119::", "", 1).rsplit("::", 1)[0] if bundle_id else packet.name,
                "bundle_id": bundle_id,
                "repo_id": "repository_library",
                "repo_family": "repository_library",
                "language_family": "python",
                "source_kind": "reviewed_bundle",
                "selected_tests_count": 0,
                "candidate_path_count": 0,
                "bundle_valid_for_eval": bool(rubric.get("bundle_valid_for_eval")),
                "same_surface_admissible": bool(anti.get("admissible_for_same_surface_comparison")),
                "gold_ready": bool(gold.get("bundle_gold_ready_for_eval")),
                "frontier_overlap": bundle_id in FRONTIER_BUNDLE_IDS,
                "same_family_as_current_miss": "mirrormind" in bundle_id.lower(),
                "claim_boundary": {
                    "review_dir": display(packet),
                },
                "notes": [str(rubric.get("decision_rationale") or "")],
            }
        )
    return rows


def bundle_row(path: Path, source_kind: str, repo_id: str) -> dict[str, Any]:
    bundle = load_json(path)
    claim_boundary = bundle.get("claim_boundary") or {}
    bundle_id = str(bundle.get("bundle_id") or "")
    selected_tests = bundle.get("selected_tests") or []
    candidate_paths = bundle.get("candidate_paths") or []
    return {
        "candidate_root_id": bundle_id.rsplit("::", 1)[0] if bundle_id else path.stem,
        "bundle_id": bundle_id,
        "repo_id": repo_id,
        "repo_family": repo_id,
        "language_family": "python",
        "source_kind": source_kind,
        "selected_tests_count": len(selected_tests),
        "candidate_path_count": len(candidate_paths),
        "bundle_valid_for_eval": bool(claim_boundary.get("same_surface_eval_admissible")),
        "same_surface_admissible": bool(claim_boundary.get("same_surface_eval_admissible")),
        "gold_ready": bool(claim_boundary.get("gold_answers_fully_adjudicated")),
        "frontier_overlap": False,
        "same_family_as_current_miss": "mirrormind" in bundle_id.lower(),
        "claim_boundary": claim_boundary,
        "notes": [
            f"selected_tests={selected_tests}",
            f"candidate_paths={candidate_paths}",
        ],
    }


def successor_rows() -> list[dict[str, Any]]:
    salvage = load_json(SUCCESSOR_SALVAGE_JSON)
    rows: list[dict[str, Any]] = []
    for row in salvage.get("targeted_admitted_rows") or []:
        if row.get("language_family") != "python":
            continue
        rows.append(
            {
                "candidate_root_id": str(row["row_id"]).rsplit("::", 1)[0],
                "bundle_id": str(row["row_id"]).rsplit("::", 1)[0] + "::python_successor",
                "repo_id": row.get("repo_id"),
                "repo_family": row.get("repo_id"),
                "language_family": "python",
                "source_kind": "adjudicated_successor_row",
                "selected_tests_count": int(row.get("selected_tests_count") or 0),
                "candidate_path_count": 0,
                "bundle_valid_for_eval": False,
                "same_surface_admissible": False,
                "gold_ready": True,
                "frontier_overlap": False,
                "same_family_as_current_miss": False,
                "claim_boundary": {
                    "successor_template": row.get("successor_template"),
                    "adjudicated_gold_answer": row.get("adjudicated_gold_answer"),
                    "review_packet_dir": row.get("review_packet_dir"),
                },
                "notes": [
                    "admitted only under successor-row contract",
                    f"adjudicated_gold_answer={row.get('adjudicated_gold_answer')}",
                ],
            }
        )
    return rows


def priority_score(row: dict[str, Any]) -> int:
    score = 0
    if row["repo_id"] not in {"repository_library"}:
        score += 6
    if row["selected_tests_count"] > 0:
        score += 4
    if row["gold_ready"]:
        score += 3
    if row["same_surface_admissible"]:
        score += 3
    if row["source_kind"] == "adjudicated_successor_row":
        score += 2
    if row["source_kind"] == "reviewed_bundle":
        score += 1
    if row["frontier_overlap"]:
        score -= 8
    if row["same_family_as_current_miss"]:
        score -= 4
    if row["source_kind"] in {"mirrormind_support_bundle", "mirrormind_exact_geometry_bundle"}:
        score -= 2
    if row["claim_boundary"].get("train_support_only"):
        score -= 1
    if row["claim_boundary"].get("adjudicated_gold_answer") == "ABSTAIN_INSUFFICIENT_EVIDENCE":
        score -= 1
    return score


def recommendation(row: dict[str, Any]) -> str:
    if row["frontier_overlap"]:
        return "frontier_root_do_not_reuse_for_disjoint_support"
    if row["same_family_as_current_miss"] and row["repo_id"] == "repository_library":
        return "same_family_support_only_not_promotable_disjoint"
    if row["source_kind"] == "adjudicated_successor_row":
        return "abstention_or_successor_support_only"
    if row["repo_id"] == "code_assist":
        return "best_disjoint_python_support_candidate"
    if row["repo_id"] == "agentkernel":
        return "secondary_disjoint_python_support_candidate"
    if row["bundle_valid_for_eval"]:
        return "reviewed_nonfrontier_candidate"
    return "needs_stronger_review_or_materialization"


def main() -> None:
    residual_queue = load_json(CURRENT_RESIDUAL_QUEUE)
    rows = review_rows()
    rows.extend(
        [
            bundle_row(PYTHON_MIRRORMIND_BUNDLE, "mirrormind_support_bundle", "repository_library"),
            bundle_row(PYTHON_MIRRORMIND_EXACT_BUNDLE, "mirrormind_exact_geometry_bundle", "repository_library"),
            bundle_row(CODE_ASSIST_CONTEXT_BUNDLE, "code_assist_context_bundle", "code_assist"),
            bundle_row(CODE_ASSIST_HF_LOCAL_BUNDLE, "code_assist_hf_local_bundle", "code_assist"),
        ]
    )
    rows.extend(successor_rows())

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["bundle_id"])
        row["priority_score"] = priority_score(row)
        row["recommendation"] = recommendation(row)
        existing = deduped.get(key)
        if existing is None or row["priority_score"] > existing["priority_score"]:
            deduped[key] = row

    ranked = sorted(deduped.values(), key=lambda row: (-row["priority_score"], row["bundle_id"]))
    top_candidates = [row for row in ranked if row["recommendation"] in {
        "best_disjoint_python_support_candidate",
        "secondary_disjoint_python_support_candidate",
        "reviewed_nonfrontier_candidate",
    }][:6]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Python disjoint-root supply atlas for the repaired v2.7 residual queue.",
            "This ranks candidate support sources; it does not itself promote any new Python benchmark win.",
        ],
        "source_artifacts": {
            "current_residual_queue": display(CURRENT_RESIDUAL_QUEUE),
            "review_packets": display(REVIEW_PACKETS),
            "mirrormind_support_bundle": display(PYTHON_MIRRORMIND_BUNDLE),
            "mirrormind_exact_bundle": display(PYTHON_MIRRORMIND_EXACT_BUNDLE),
            "code_assist_context_bundle": display(CODE_ASSIST_CONTEXT_BUNDLE),
            "code_assist_hf_local_bundle": display(CODE_ASSIST_HF_LOCAL_BUNDLE),
            "successor_salvage": display(SUCCESSOR_SALVAGE_JSON),
        },
        "current_python_residual": next(
            (row for row in residual_queue.get("targets") or [] if row.get("language_family") == "python"),
            None,
        ),
        "summary": {
            "candidate_count": len(ranked),
            "top_disjoint_code_assist_candidates": sum(1 for row in ranked if row["repo_id"] == "code_assist"),
            "same_family_repository_library_candidates": sum(1 for row in ranked if row["repo_id"] == "repository_library"),
            "agentkernel_successor_candidates": sum(1 for row in ranked if row["repo_id"] == "agentkernel"),
        },
        "top_candidates": top_candidates,
        "claim_boundary": [
            "Repository-library Mirrormind support remains useful for training diagnostics but is not a promotable disjoint rebuild path for the current Python verifier miss.",
            "The best current disjoint Python supply is code_assist-rooted and selected-test anchored.",
            "Agentkernel successor rows are honesty/support candidates, not direct same-surface replacements for maintainer bundles.",
        ],
        "recommended_next_step": "Materialize a compact Python residual-support package from the top code_assist disjoint candidates first, then use agentkernel successor rows only as abstention/honesty support.",
        "outputs": {
            "atlas_json": display(ATLAS_JSON),
            "rows_jsonl": display(ROWS_JSONL),
        },
    }

    write_json(ATLAS_JSON, payload)
    write_jsonl(ROWS_JSONL, ranked)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
