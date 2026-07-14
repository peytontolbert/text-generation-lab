from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10505_multilingual_residual_root_scaling_queue"

PYTHON_PACKET = ROOT / "runs/local/artifacts/stage10493_python_verifier_fresh_review_packet_builder/python_verifier_fresh_review_packet_builder.json"
PYTHON_TARGETS = ROOT / "runs/local/artifacts/stage10493_python_verifier_fresh_review_packet_builder/python_verifier_review_target_status.jsonl"
PYTHON_QUEUE = ROOT / "runs/local/artifacts/stage10492_python_verifier_reviewed_root_expansion_queue/python_verifier_reviewed_root_expansion_queue.json"
RUST_BUILDER = ROOT / "runs/local/artifacts/stage10467_rust_citation_fresh_root_builder/rust_citation_fresh_root_builder.json"
RUST_TARGETS = ROOT / "runs/local/artifacts/stage10467_rust_citation_fresh_root_builder/rust_citation_fresh_root_targets.jsonl"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"
LATEST_PYTHON_AUDIT = ROOT / "runs/local/artifacts/stage10504_context_pack_plus_hf_local_probe_audit/context_pack_plus_hf_local_probe_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def classify_python_target(row: dict[str, Any]) -> tuple[str, list[str]]:
    gaps = row.get("gaps", [])
    if row.get("immediately_qualified_for_reviewed_verifier_packet"):
        return "execution_ready_promotable_support", []
    blockers = []
    if "reviewed_verifier_target_set_too_small" in gaps:
        blockers.append("verifier_target_set_too_small")
    if "queue_reviewed_selected_test_mismatch" in gaps:
        blockers.append("selected_test_competition_weaker_than_queue")
    if "missing_perspective_gold_adjudication" in gaps:
        blockers.append("missing_gold_adjudication")
    if "missing_verifier_outcome_gold" in gaps:
        blockers.append("missing_verifier_outcome_gold")
    if "no_executable_verifier_rows_present" in gaps:
        blockers.append("no_bounded_executable_verifier_rows")
    status = "blocked_requires_packet_rebuild"
    if row.get("has_rubric_review") and row.get("has_anti_cheat_review") and not row.get("has_gold_adjudication"):
        status = "honesty_only_until_gold_materialized"
    return status, blockers


def classify_rust_target(row: dict[str, Any]) -> tuple[str, list[str]]:
    support_role = row.get("support_role")
    blockers: list[str] = []
    if support_role == "fresh_root_builder_target":
        blockers.extend(
            [
                "no_review_packet_built",
                "no_selected_test_or_verifier_anchor_materialized",
                "no_executable_bounded_rows",
            ]
        )
        return "builder_target_not_yet_materialized", blockers
    if support_role == "diagnostic_train_support_only":
        blockers.append("not_a_true_e_vs_f_disjoint_root")
        return "diagnostic_only_train_support", blockers
    return "unknown", blockers


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    python_packet = load_json(PYTHON_PACKET)
    python_targets = load_jsonl(PYTHON_TARGETS)
    python_queue = load_json(PYTHON_QUEUE)
    rust_builder = load_json(RUST_BUILDER)
    rust_targets = load_jsonl(RUST_TARGETS)
    promotion_gate = load_json(PROMOTION_GATE)
    latest_python_audit = load_json(LATEST_PYTHON_AUDIT)

    target_rows: list[dict[str, Any]] = []

    for row in python_targets:
        status, blockers = classify_python_target(row)
        target_rows.append(
            {
                "language_family": "python",
                "residual_family": "verifier_target_disambiguation",
                "bundle_id": row["bundle_id"],
                "repo_id": row["repo_id"],
                "priority_order": row["priority_order"],
                "status": status,
                "selected_tests_count": row["reviewed_selected_tests_count"],
                "executable_verifier_row_count": row["executable_verifier_row_count"],
                "gold_verifier_target": row.get("reviewed_verifier_gold_value"),
                "blockers": blockers,
                "supports_promotable_packet": status == "execution_ready_promotable_support",
                "source_artifact": str(PYTHON_TARGETS.relative_to(ROOT)),
            }
        )

    for row in rust_targets:
        status, blockers = classify_rust_target(row)
        target_rows.append(
            {
                "language_family": "rust",
                "residual_family": "evidence_support_disambiguation",
                "bundle_id": row["candidate_root_id"],
                "repo_id": row["repo_id"],
                "priority_order": row["priority_order"],
                "status": status,
                "selected_tests_count": row["test_file_count"],
                "competition_geometries": row["competition_geometries"],
                "blockers": blockers,
                "supports_promotable_packet": False,
                "source_artifact": str(RUST_TARGETS.relative_to(ROOT)),
            }
        )

    execution_ready = [row for row in target_rows if row["status"] == "execution_ready_promotable_support"]
    builder_blocked = [row for row in target_rows if row["status"] == "builder_target_not_yet_materialized"]
    honesty_only = [row for row in target_rows if row["status"] == "honesty_only_until_gold_materialized"]
    packet_blocked = [row for row in target_rows if row["status"] == "blocked_requires_packet_rebuild"]
    diagnostic_only = [row for row in target_rows if row["status"] == "diagnostic_only_train_support"]

    summary = {
        "stage": 10505,
        "stage_name": "stage10505_multilingual_residual_root_scaling_queue",
        "created_from": {
            "python_packet_builder": str(PYTHON_PACKET.relative_to(ROOT)),
            "python_queue": str(PYTHON_QUEUE.relative_to(ROOT)),
            "rust_builder": str(RUST_BUILDER.relative_to(ROOT)),
            "promotion_gate": str(PROMOTION_GATE.relative_to(ROOT)),
            "latest_python_probe_audit": str(LATEST_PYTHON_AUDIT.relative_to(ROOT)),
        },
        "current_frontier_status": {
            "strict_accuracy": latest_python_audit["accuracy"]["probe"],
            "baseline_accuracy": latest_python_audit["accuracy"]["baseline"],
            "beats_frontier": latest_python_audit["headline"]["beats_live_baseline"],
            "residual_miss_set_changed": latest_python_audit["headline"]["residual_miss_set_changed"],
            "promotion_gate_passed": promotion_gate["passed"],
        },
        "current_residuals": {
            "python": python_queue["current_python_residual"],
            "rust": rust_builder["current_residual_target"],
        },
        "queue_summary": {
            "execution_ready_promotable_support": len(execution_ready),
            "blocked_requires_packet_rebuild": len(packet_blocked),
            "builder_target_not_yet_materialized": len(builder_blocked),
            "honesty_only_until_gold_materialized": len(honesty_only),
            "diagnostic_only_train_support": len(diagnostic_only),
        },
        "next_best_actions": [
            "Use the stage10236 context_pack Python root as the only immediately executable promotable disjoint verifier support bundle.",
            "Repair or expand the stage10300 hf_local verifier packet so it exposes 3 or more plausible verifier targets before reusing it in a promotable packet.",
            "Materialize at least one non-tokenizers Rust review packet from linux, candle-datasets, or candle-transformers before claiming fresh-root Rust residual progress.",
            "Keep candle-core Rust rows as diagnostic train support only and keep tokenizers same-surface rows out of promotable support.",
            "Require a fresh disjoint-root success artifact plus strict accuracy > 22/24 before any new frontier promotion.",
        ],
        "required_honesty_gates": [
            "No same-root replay from the current MirrorMind strict row into train support.",
            "No tokenizers same-surface strict row may enter promotable train support.",
            "Every new Python or Rust residual packet must pass prompt_target_leak false before execution.",
            "Do not count abstention-only successor rows as verifier-disambiguation capability support.",
            "A future promotion candidate must attach a fresh disjoint-root comparison artifact, not only same-manifest strict eval.",
        ],
        "recommended_next_stages": [
            "stage10506_python_verifier_packet_geometry_rebuild",
            "stage10507_rust_evidence_citation_non_tokenizers_packet_builder",
            "stage10508_fresh_residual_root_comparison_gate",
        ],
    }

    (ARTIFACT_DIR / "multilingual_residual_root_scaling_queue.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (ARTIFACT_DIR / "multilingual_residual_root_scaling_targets.jsonl").open("w", encoding="utf-8") as handle:
        for row in sorted(target_rows, key=lambda item: (item["language_family"], item["priority_order"])):
            handle.write(json.dumps(row, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
