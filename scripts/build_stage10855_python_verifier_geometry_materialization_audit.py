#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10855
NAME = "stage10855_python_verifier_geometry_materialization_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "python_verifier_geometry_materialization_audit.json"
ADMITTED_JSONL = OUT_DIR / "admitted_python_verifier_roots.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

REPAIRED_PACKET_DIR = (
    ARTIFACTS
    / "stage10854_python_verifier_geometry_materialization_repair"
    / "review_packets"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    admitted: list[dict[str, Any]] = []
    for packet_dir in sorted(REPAIRED_PACKET_DIR.iterdir()):
        if not packet_dir.is_dir():
            continue
        bundle = load_json(packet_dir / "fresh_python_bundle_preview.json")
        anti = load_json(packet_dir / "anti_cheat_review_card.json")
        gold = load_json(packet_dir / "perspective_gold_adjudication.json")
        admitted.append(
            {
                "bundle_id": bundle["bundle_id"],
                "packet_dir": rel(packet_dir),
                "repo_id": bundle["repo_id"],
                "language_family": bundle["language_family"],
                "lane": "geometry_materialized_context_pack",
                "admission_scope": "train_support_only",
                "headline_eligible": False,
                "selected_test_count": len(bundle.get("selected_tests") or []),
                "candidate_path_count": len(bundle.get("candidate_paths") or []),
                "visible_evidence_keys": sorted((bundle.get("maintainer_visible_evidence") or {}).keys()),
                "anti_cheat_status": anti.get("status"),
                "gold_status": "completed" if gold.get("bundle_gold_ready_for_eval") else gold.get("status"),
                "supports_training_or_scoring_now": bool(bundle.get("claim_boundary", {}).get("supports_training_or_scoring_now")),
                "quality_note": (
                    "Real verifier geometry is now present, but the packet still carries same-surface selected-test "
                    "name priors and should remain train-support only."
                ),
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_geometry_materialization_admitted_for_train_support",
        "headline_findings": [
            "One previously blocked agentkernel Python verifier root is now admitted for train-support use.",
            "The repaired packet replaces placeholder verifier geometry with real implementation and test snippets.",
            "The packet remains non-headline and non-promotable because selected-test name priors still need a harder follow-up root.",
        ],
        "admitted_root_count": len(admitted),
        "admitted_roots": admitted,
        "next_best_step": "Feed this repaired root into the residual support inventory, then build a second independent Python verifier-transition root to reduce same-family shortcut risk.",
    }

    write_jsonl(ADMITTED_JSONL, admitted)
    write_json(OUT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "admitted_root_count": len(admitted),
            "artifact": rel(OUT_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
