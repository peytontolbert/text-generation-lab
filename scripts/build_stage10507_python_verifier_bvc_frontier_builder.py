from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10507_python_verifier_bvc_frontier_builder"

FRONTIER_REQUEST = ROOT / "runs/local/artifacts/stage10506_fresh_python_rust_frontier_request/fresh_python_rust_frontier_request.json"
SCALING_TARGETS = ROOT / "runs/local/artifacts/stage10505_multilingual_residual_root_scaling_queue/multilingual_residual_root_scaling_targets.jsonl"
CONTEXT_PACK_BUNDLE = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/context_pack_python_replenishment_bundle.json"
HF_LOCAL_BUNDLE = ROOT / "runs/local/artifacts/stage10300_hf_local_python_replenishment_bundle/hf_local_python_replenishment_bundle.json"
AGENTKERNEL_SUCCESSORS = ROOT / "runs/local/artifacts/stage10410_ai_adjudicated_successor_salvage/real_session_successor_adjudicated_manifest.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def perspective_seed_rows(bundle: dict[str, Any], bundle_role: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for perspective in bundle.get("perspective_rows", []):
        contract = perspective.get("prompt_contract", {})
        rows.append(
            {
                "bundle_id": perspective["bundle_id"],
                "bundle_role": bundle_role,
                "language_family": perspective["language_family"],
                "perspective": perspective["perspective"],
                "candidate_path_count": len(contract.get("candidate_paths", [])),
                "selected_tests_count": len(contract.get("selected_tests", [])),
                "selected_tests": contract.get("selected_tests", []),
                "abstention_option_required": contract.get("abstention_option_required", False),
                "task": contract.get("task"),
                "visible_evidence_keys": contract.get("visible_evidence_keys", []),
                "eligible_for_training_or_scoring_now": perspective.get("eligible_for_training_or_scoring_now"),
                "gold_answer_status": perspective.get("gold_answer_status"),
            }
        )
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    frontier_request = load_json(FRONTIER_REQUEST)
    scaling_targets = [row for row in load_jsonl(SCALING_TARGETS) if row["language_family"] == "python"]
    context_pack = load_json(CONTEXT_PACK_BUNDLE)
    hf_local = load_json(HF_LOCAL_BUNDLE)
    successors = [
        row
        for row in load_jsonl(AGENTKERNEL_SUCCESSORS)
        if row.get("language_family") == "python"
        and row.get("source_bundle_id", "").startswith("stage10110::localsess_agentkernel")
    ]

    ready_targets = [row for row in scaling_targets if row["status"] == "execution_ready_promotable_support"]
    blocked_targets = [row for row in scaling_targets if row["status"] == "blocked_requires_packet_rebuild"]
    honesty_only_targets = [row for row in scaling_targets if row["status"] == "honesty_only_until_gold_materialized"]

    seed_rows = perspective_seed_rows(context_pack, "execution_ready_seed") + perspective_seed_rows(
        hf_local, "geometry_rebuild_seed"
    )

    summary = {
        "stage": 10507,
        "stage_name": "stage10507_python_verifier_bvc_frontier_builder",
        "frontier_contract": frontier_request["frontiers"]["python_verifier_bvc_frontier_v1"],
        "seed_supply_summary": {
            "execution_ready_bundle_ids": [row["bundle_id"] for row in ready_targets],
            "blocked_bundle_ids": [row["bundle_id"] for row in blocked_targets],
            "honesty_only_bundle_ids": [row["bundle_id"] for row in honesty_only_targets],
            "seed_perspective_rows": len(seed_rows),
            "seed_verifier_rows": sum(1 for row in seed_rows if row["perspective"] == "verifier_outcome"),
            "seed_bundles": 2,
        },
        "builder_plan": [
            "Use stage10236 context_pack as the first executable B-vs-C seed family because it already exposes four selected tests and one verifier_outcome row with sibling competition.",
            "Treat stage10300 hf_local as geometry-rebuild seed only until it is expanded beyond a single selected test.",
            "Carry agentkernel successor rows only as abstention-honesty references; they do not count toward verifier frontier scale.",
            "Expand by root, not by permutation: each new root should add new verifier_outcome competition, not just rephrased evidence.",
        ],
        "required_row_contract": [
            "perspective == verifier_outcome",
            "at least 3 plausible test options",
            "selected_test_anchor present but not leaked verbatim before options",
            "candidate_change_surface and nearby context should tempt different tests",
            "heldout rows must include same-family hard negatives",
        ],
        "expansion_targets": {
            "row_budget_min": frontier_request["frontiers"]["python_verifier_bvc_frontier_v1"]["row_budget"]["min"],
            "row_budget_max": frontier_request["frontiers"]["python_verifier_bvc_frontier_v1"]["row_budget"]["max"],
            "bundle_seed_quota": {
                "stage10236_context_pack": 1,
                "stage10300_hf_local_rebuild": 1,
                "new_disjoint_roots_required_beyond_existing_seed": "at least 6",
            },
        },
        "blocked_geometry_reasons": blocked_targets,
        "honesty_only_references": [
            {
                "source_bundle_id": row.get("source_bundle_id"),
                "row_id": row.get("row_id"),
                "gold_value": row.get("gold_value"),
            }
            for row in successors[:8]
        ],
    }

    (ARTIFACT_DIR / "python_verifier_bvc_frontier_builder.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (ARTIFACT_DIR / "python_verifier_bvc_seed_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in seed_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
