#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10757
NAME = "stage10757_residual_packet_materialization_backlog"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "residual_packet_materialization_backlog.json"
BACKLOG_JSONL = OUT_DIR / "materialization_backlog.jsonl"
DEPENDENCIES_JSONL = OUT_DIR / "source_dependency_map.jsonl"
RUNBOOK_JSONL = OUT_DIR / "promotion_guardrails.jsonl"
RUN_SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

READINESS_QUEUE_JSONL = ARTIFACTS / "stage10755_python_rust_residual_review_readiness_queue" / "residual_review_queue.jsonl"
PYTHON_SCAFFOLD_SUMMARY = ARTIFACTS / "stage10756_python_verifier_geometry_upgrade_scaffolds" / "python_verifier_geometry_upgrade_scaffolds.json"
PYTHON_SCAFFOLD_DIR = ARTIFACTS / "stage10756_python_verifier_geometry_upgrade_scaffolds" / "review_packets"
RUST_SCAFFOLD_SUMMARY = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds" / "rust_fresh_review_packet_scaffolds.json"
RUST_SCAFFOLD_DIR = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds" / "review_packets"
ROOT_SCALE_SUMMARY = ARTIFACTS / "stage10754_multilingual_root_scale_package_v3" / "multilingual_root_scale_package_v3.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def packet_index(root: Path) -> tuple[dict[str, Path], list[tuple[str, Path]]]:
    indexed: dict[str, Path] = {}
    bundle_pairs: list[tuple[str, Path]] = []
    if not root.exists():
        return indexed, bundle_pairs
    for packet_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        preview_path = packet_dir / "fresh_python_bundle_preview.json"
        if not preview_path.exists():
            preview_path = packet_dir / "fresh_rust_bundle_preview.json"
        if not preview_path.exists():
            continue
        payload = load_json(preview_path)
        bundle_id = str(payload.get("bundle_id") or "")
        if bundle_id:
            indexed[bundle_id] = packet_dir
            bundle_pairs.append((bundle_id, packet_dir))
    return indexed, bundle_pairs


def resolve_packet_dir(bundle_id: str, candidate_id: str, direct_index: dict[str, Path], bundle_pairs: list[tuple[str, Path]]) -> Path | None:
    if bundle_id in direct_index:
        return direct_index[bundle_id]
    for known_bundle_id, packet_dir in bundle_pairs:
        if candidate_id and candidate_id in known_bundle_id:
            return packet_dir
    return None


def load_preview(packet_dir: Path) -> dict[str, Any]:
    for name in ("fresh_python_bundle_preview.json", "fresh_rust_bundle_preview.json"):
        path = packet_dir / name
        if path.exists():
            return load_json(path)
    raise FileNotFoundError(f"no preview bundle under {packet_dir}")


def language_guardrail(language: str) -> str:
    if language == "python":
        return "Promotable only after richer verifier geometry is materialized with 3+ plausible selected tests and refreshed gold adjudication."
    if language == "rust":
        return "Diagnostic-only until real source spans and a verifier/test anchor replace placeholders."
    return "Do not promote until review and anti-cheat gates are complete."


def action_rank(readiness: str, language: str) -> int:
    if language == "python" and readiness == "deferred":
        return 1
    if language == "rust" and readiness == "scaffold_only":
        return 2
    if language == "python" and readiness == "immediately_qualified":
        return 3
    return 9


def main() -> None:
    readiness_rows = load_jsonl(READINESS_QUEUE_JSONL)
    python_summary = load_json(PYTHON_SCAFFOLD_SUMMARY)
    rust_summary = load_json(RUST_SCAFFOLD_SUMMARY)
    root_scale = load_json(ROOT_SCALE_SUMMARY)

    python_packets, python_bundle_pairs = packet_index(PYTHON_SCAFFOLD_DIR)
    rust_packets, rust_bundle_pairs = packet_index(RUST_SCAFFOLD_DIR)

    backlog_rows: list[dict[str, Any]] = []
    dependency_rows: list[dict[str, Any]] = []

    for row in readiness_rows:
        language = str(row["language_family"])
        readiness = str(row["readiness"])
        bundle_id = str(row["bundle_id"])
        candidate_id = str(row["candidate_id"])
        packet_dir: Path | None = None
        preview: dict[str, Any] | None = None

        packet_dir = resolve_packet_dir(bundle_id, candidate_id, python_packets, python_bundle_pairs)
        if packet_dir is None:
            packet_dir = resolve_packet_dir(bundle_id, candidate_id, rust_packets, rust_bundle_pairs)
        if packet_dir is not None:
            preview = load_preview(packet_dir)

        candidate_paths = []
        selected_tests = []
        visible_keys = []
        if isinstance(preview, dict):
            candidate_paths = list(preview.get("candidate_paths") or [])
            if not candidate_paths:
                for item in list((preview.get("maintainer_visible_evidence") or {}).get("candidate_change_surface") or []):
                    path = item.get("path")
                    if path:
                        candidate_paths.append(str(path))
            selected_tests = list(preview.get("selected_tests") or [])
            if not selected_tests:
                for item in list((preview.get("maintainer_visible_evidence") or {}).get("verifier_and_test_constraint") or []):
                    path = item.get("path")
                    if path:
                        selected_tests.append(str(path))
            visible_keys = sorted(list((preview.get("maintainer_visible_evidence") or {}).keys()))

        missing_fields = []
        if language == "python" and readiness == "deferred":
            missing_fields = list(python_summary.get("required_materialization_fields") or [])
        elif language == "rust" and readiness == "scaffold_only":
            missing_fields = list(rust_summary.get("required_materialization_fields") or [])
        elif language == "python" and readiness == "immediately_qualified":
            missing_fields = [
                "keep this lane train-support only until fresh heldout verifier roots exist",
                "do not promote as residual recovery by itself because earlier context-pack-only probe preserved but did not improve the strict frontier",
            ]

        backlog_rows.append(
            {
                "action_rank": action_rank(readiness, language),
                "language_family": language,
                "readiness": readiness,
                "work_type": str(row["work_type"]),
                "bundle_id": bundle_id,
                "candidate_id": str(row["candidate_id"]),
                "repo_id": str(row["repo_id"]),
                "packet_dir": rel(packet_dir) if packet_dir else None,
                "preview_bundle_present": bool(packet_dir),
                "candidate_path_count": len(candidate_paths),
                "selected_test_or_anchor_count": len(selected_tests),
                "visible_evidence_keys": visible_keys,
                "anti_cheat_gates": list(row.get("anti_cheat_gates") or []),
                "missing_materialization_fields": missing_fields,
                "next_action": str(row["next_action"]),
                "promotion_boundary": language_guardrail(language),
                "scoring_status": "not_scoreable" if readiness in {"deferred", "scaffold_only"} else "train_support_only",
            }
        )

        dependency_rows.append(
            {
                "bundle_id": bundle_id,
                "language_family": language,
                "repo_id": str(row["repo_id"]),
                "source_artifact": str(row["source_artifact"]),
                "packet_preview": rel(packet_dir / ("fresh_python_bundle_preview.json" if language == "python" and packet_dir and (packet_dir / "fresh_python_bundle_preview.json").exists() else "fresh_rust_bundle_preview.json")) if packet_dir else None,
                "anti_cheat_review_card": rel(packet_dir / "anti_cheat_review_card.json") if packet_dir and (packet_dir / "anti_cheat_review_card.json").exists() else None,
                "perspective_gold_adjudication": rel(packet_dir / "perspective_gold_adjudication.json") if packet_dir and (packet_dir / "perspective_gold_adjudication.json").exists() else None,
                "candidate_paths": candidate_paths,
                "selected_tests_or_anchors": selected_tests,
            }
        )

    backlog_rows.sort(key=lambda item: (item["action_rank"], item["language_family"], item["bundle_id"]))

    guardrails = [
        {
            "language_family": "python",
            "promotion_guardrail": "Do not spend probe cycles on the deferred hf_local or agentkernel packets until real verifier/test evidence is attached and gold adjudication is refreshed.",
            "current_state": "one qualified support root plus two deferred richer-geometry packets",
            "next_best_move": "materialize the two deferred packets rather than replay the already-tested context-pack lane",
        },
        {
            "language_family": "rust",
            "promotion_guardrail": "Keep all current Rust residual packets diagnostic-only until real source spans and verifier anchors replace the placeholders.",
            "current_state": "three scaffold packets and no promotable fresh residual packet",
            "next_best_move": "fill at least one scaffold with real evidence and rerun anti-cheat before any training or comparison claim",
        },
        {
            "language_family": "cross_language",
            "promotion_guardrail": "A packet existing on disk is not a capability improvement. Only scoreable, anti-cheat-clean, source-materialized packets count as new residual supply.",
            "current_state": "standalone strict frontier remains 22/24; residual supply is the bottleneck",
            "next_best_move": "treat this backlog as the packet-construction gate for the next Python/Rust residual package refresh",
        },
    ]

    scale_counts = (root_scale.get("global_counts") or {}).get("ready_for_large_scale_train_by_language") or {}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_packet_materialization_backlog_ready",
        "claim_scope": [
            "Turn the current Python verifier and Rust evidence residual lanes into an explicit packet-materialization backlog.",
            "Separate support-ready, geometry-upgrade, and scaffold-only lanes so future package refreshes stop treating all residual packets as equally executable.",
            "This is a packet-construction and promotion-boundary artifact, not a new model score claim.",
        ],
        "headline_findings": [
            "Python has one train-support-ready verifier root, but the two deferred richer-geometry packets remain the real promotable residual supply work.",
            "Rust still has only scaffold packets; none are scoreable until real source spans and verifier anchors are attached.",
            "The strict 22/24 frontier is therefore blocked by packet materialization quality, not by another small support blend.",
        ],
        "queue_counts": {
            "total_backlog_items": len(backlog_rows),
            "python_deferred_geometry_upgrades": sum(1 for row in backlog_rows if row["language_family"] == "python" and row["readiness"] == "deferred"),
            "python_support_ready_reference_lanes": sum(1 for row in backlog_rows if row["language_family"] == "python" and row["readiness"] == "immediately_qualified"),
            "rust_scaffold_materialization_lanes": sum(1 for row in backlog_rows if row["language_family"] == "rust" and row["readiness"] == "scaffold_only"),
        },
        "ready_for_large_scale_train_by_language": scale_counts,
        "source_artifacts": {
            "readiness_queue": rel(READINESS_QUEUE_JSONL),
            "python_scaffold_summary": rel(PYTHON_SCAFFOLD_SUMMARY),
            "rust_scaffold_summary": rel(RUST_SCAFFOLD_SUMMARY),
            "root_scale_summary": rel(ROOT_SCALE_SUMMARY),
        },
        "next_best_step": "Materialize the two deferred Python verifier packets and at least one Rust scaffold packet with real evidence, then rerun anti-cheat and gold adjudication before any new probe request.",
        "outputs": {
            "summary": rel(SUMMARY_JSON),
            "backlog": rel(BACKLOG_JSONL),
            "dependency_map": rel(DEPENDENCIES_JSONL),
            "promotion_guardrails": rel(RUNBOOK_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(BACKLOG_JSONL, backlog_rows)
    write_jsonl(DEPENDENCIES_JSONL, dependency_rows)
    write_jsonl(RUNBOOK_JSONL, guardrails)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "summary": rel(SUMMARY_JSON),
            "backlog": rel(BACKLOG_JSONL),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
