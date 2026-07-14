#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10850
NAME = "stage10850_residual_frontier_root_build_queue"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "residual_frontier_root_build_queue.json"
QUEUE_JSONL = OUT_DIR / "residual_frontier_root_build_tasks.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

PY_QUEUE = ARTIFACTS / "stage10714_python_verifier_contrast_creation_queue" / "python_verifier_contrast_tasks.jsonl"
RUST_PENDING = ARTIFACTS / "stage10726_rust_citation_semantic_contrast_builder" / "rust_citation_semantic_pending_roots.jsonl"
REBALANCE_REQUEST = ARTIFACTS / "stage10843_residual_family_rebalance_request" / "residual_family_rebalance_request.json"
PROBE_AUDIT = ARTIFACTS / "stage10848_residual_family_rebalanced_probe_audit" / "residual_family_rebalanced_probe_audit.json"
SCORING_AUDIT = ARTIFACTS / "stage10849_current_runtime_scoring_policy_audit" / "current_runtime_scoring_policy_audit.json"


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
    py_queue = load_jsonl(PY_QUEUE)
    rust_pending = load_jsonl(RUST_PENDING)
    rebalance_request = load_json(REBALANCE_REQUEST)
    probe_audit = load_json(PROBE_AUDIT)
    scoring_audit = load_json(SCORING_AUDIT)

    tasks: list[dict[str, Any]] = []

    for task in py_queue:
        tasks.append(
            {
                "priority": 1,
                "language_family": "python",
                "task_family": "verifier_outcome",
                "task_id": "fresh_python_verifier_transition_roots_v1",
                "source_reference": task["task_id"],
                "required_root_count": 6,
                "required_row_floor": rebalance_request["residual_targets"]["python_verifier_outcome"]["requested_scale_floor"],
                "must_include": [
                    "multi-option verifier rows with B/C/G-like targets",
                    "test snippet plus changed-code-path evidence",
                    "explicit transition semantics: FAIL_TO_PASS, PASS_TO_PASS, NOT_EXERCISED, INSUFFICIENT_EVIDENCE",
                    "at least one close sibling wrong test candidate per root",
                ],
                "must_avoid": [
                    "same-root permutations",
                    "literal gold test path before options",
                    "singleton verifier rows",
                    "strict-root reuse",
                ],
                "why_now": [
                    "strict Python residual remains wrong after stage10847",
                    "current scorer policy audit shows no scoring fix improves the Python verifier row",
                ],
                "recommended_next_stage": "stage10851_fresh_python_verifier_transition_root_builder",
            }
        )

    rust_candidates = [row for row in rust_pending if row.get("repo_id") != "tokenizers"][:4]
    tasks.append(
        {
            "priority": 2,
            "language_family": "rust",
            "task_family": "evidence_citation",
            "task_id": "fresh_rust_ef_evidence_roots_v1",
            "candidate_roots": rust_candidates,
            "required_root_count": 2,
            "required_row_floor": rebalance_request["residual_targets"]["rust_evidence_citation"]["requested_scale_floor"],
            "must_include": [
                "explicit B/C/D/E/F evidence-role coverage",
                "distinct source spans for surface, nearby, symptom-call-path, verifier constraint, and background roles",
                "candidate_change_surface as tempting negative but not gold in at least one E/F contrast",
                "fresh non-tokenizers anchored roots",
            ],
            "must_avoid": [
                "tokenizers strict-root replay",
                "duplicate text under multiple visible roles unless role reasoning is explicit",
                "support rows without verifier or selected-test anchor provenance",
            ],
            "why_now": [
                "strict Rust residual remains wrong under constrained scoring while full-vocab top1 is correct",
                "current scoring-policy audit shows no scorer policy beats raw encoder retrieval overall",
            ],
            "recommended_next_stage": "stage10852_fresh_rust_ef_evidence_root_builder",
        }
    )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_frontier_root_build_queue_ready",
        "headline_findings": [
            "Stage10847 did not improve the 22/24 strict frontier and regressed eval to 21/24.",
            "Stage10849 shows no honest scorer policy beats the current raw encoder-option-retrieval baseline on the 10847 runtime.",
            "The next productive path is fresh root construction for Python verifier transitions and Rust E/F evidence roles, not more scorer or preservation probing.",
        ],
        "authoritative_inputs": {
            "rebalance_request": rel(REBALANCE_REQUEST),
            "probe_audit": rel(PROBE_AUDIT),
            "scoring_audit": rel(SCORING_AUDIT),
            "python_queue": rel(PY_QUEUE),
            "rust_pending_queue": rel(RUST_PENDING),
        },
        "tasks": tasks,
        "recommended_stage_sequence": [
            "stage10851_fresh_python_verifier_transition_root_builder",
            "stage10852_fresh_rust_ef_evidence_root_builder",
            "stage10853_fresh_residual_root_admission_and_packet_builder",
        ],
    }

    write_jsonl(QUEUE_JSONL, tasks)
    write_json(OUT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "task_count": len(tasks),
            "artifact": rel(OUT_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
