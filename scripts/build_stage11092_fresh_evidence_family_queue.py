#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11092
NAME = "stage11092_fresh_evidence_family_queue"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_evidence_family_queue.json"
QUEUE_ROWS_JSONL = OUT_DIR / "queue_rows.jsonl"
FAMILY_ATLAS_JSONL = OUT_DIR / "family_atlas.jsonl"

TOP_SEEDS = ARTIFACTS / "stage11026_multilingual_fresh_source_acquisition_atlas" / "top_seed_rows.jsonl"
ROOT_RECORDS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_root_records.jsonl"
CAUSAL_STATES = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_causal_states.jsonl"
MULTITARGET_ROWS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_multitarget_rows.jsonl"
READY_BUNDLES = ARTIFACTS / "stage11026_multilingual_fresh_source_acquisition_atlas" / "ready_bundle_rows.jsonl"

EXHAUSTED_REPO_FAMILIES = {
    "repository_library",
    "parametergolf",
    "tokenizers",
    "candle",
    "agentkernel",
    "code_assist",
    "agentkernel-seq2seq-text-lab",
}
PREFERRED_FAMILIES = {
    "python": ["faiss", "diffusers", "django", "openai-agents-python"],
    "c_cpp": ["onnxruntime", "cccl", "cuEmbed", "falco"],
    "web_js_ts_html": ["mem0"],
}
MAX_ROOTS_PER_FAMILY = 2


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
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    top_seed_rows = load_jsonl(TOP_SEEDS)
    root_records = load_jsonl(ROOT_RECORDS)
    states_by_root = {
        str(row.get("root_id") or ""): row for row in load_jsonl(CAUSAL_STATES)
    }
    rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in load_jsonl(MULTITARGET_ROWS):
        rows_by_root[str(row.get("root_id") or "")].append(row)
    ready_bundles = load_jsonl(READY_BUNDLES)

    eligible_families = {
        (str(row.get("language_family") or ""), str(row.get("repo_family") or "")): row
        for row in top_seed_rows
        if str(row.get("repo_family") or "") not in EXHAUSTED_REPO_FAMILIES
        and str(row.get("repo_family") or "") in PREFERRED_FAMILIES.get(str(row.get("language_family") or ""), [])
    }

    family_rows: list[dict[str, Any]] = []
    queue_rows: list[dict[str, Any]] = []

    roots_grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for root in root_records:
        key = (str(root.get("language_family") or ""), str(root.get("repo_family") or ""))
        if key not in eligible_families:
            continue
        state = states_by_root.get(str(root.get("root_id") or ""))
        if state is None:
            continue
        final_state = dict(state.get("final_state") or {})
        verification_targets = list(final_state.get("verification_targets") or [])
        if not verification_targets:
            continue
        subtypes = {str(row.get("target_subtype") or "") for row in rows_by_root.get(str(root.get("root_id") or ""), [])}
        if "decisive_evidence" not in subtypes and "verifier_outcome" not in subtypes:
            continue
        roots_grouped[key].append(
            {
                "root": root,
                "state": state,
                "subtypes": sorted(subtypes),
                "verification_targets": verification_targets,
                "expected_changed_files": list(final_state.get("expected_changed_files") or []),
                "key_symbols": list(final_state.get("key_symbols") or []),
            }
        )

    priority = 1
    for language_family, repo_families in PREFERRED_FAMILIES.items():
        for repo_family in repo_families:
            key = (language_family, repo_family)
            candidates = roots_grouped.get(key, [])
            candidates = sorted(
                candidates,
                key=lambda item: (
                    0 if str(item["root"].get("split_component") or "").startswith("audited") else 1,
                    -len(item["verification_targets"]),
                    str(item["root"].get("root_id") or ""),
                ),
            )[:MAX_ROOTS_PER_FAMILY]
            if not candidates:
                family_rows.append(
                    {
                        "language_family": language_family,
                        "repo_family": repo_family,
                        "status": "missing_compiled_candidates",
                        "selected_root_count": 0,
                        "why_selected": "preferred_fresh_family_but_no_current_compiled_root_with_verifier_targets",
                    }
                )
                continue

            family_rows.append(
                {
                    "language_family": language_family,
                    "repo_family": repo_family,
                    "status": "queued",
                    "selected_root_count": len(candidates),
                    "compiled_root_count": int((eligible_families[key] or {}).get("compiled_root_count") or 0),
                    "why_selected": "fresh_family_outside_exhausted_repo_families_with_verifier_target_signal",
                }
            )

            for item in candidates:
                root = item["root"]
                state = item["state"]
                queue_rows.append(
                    {
                        "priority": priority,
                        "language_family": language_family,
                        "repo_family": repo_family,
                        "repo_id": root.get("repo_id"),
                        "root_id": root.get("root_id"),
                        "snapshot_id": root.get("snapshot_id"),
                        "source_family_id": (root.get("provenance") or {}).get("source_family_id"),
                        "split_component": root.get("split_component"),
                        "task_family": root.get("task_family"),
                        "verifier_id": root.get("verifier_id"),
                        "claim_role": "fresh_family_materialization_candidate",
                        "query_text": state.get("query_text"),
                        "verification_targets": item["verification_targets"],
                        "expected_changed_files": item["expected_changed_files"],
                        "key_symbols": item["key_symbols"][:12],
                        "available_target_subtypes": item["subtypes"],
                        "materialization_requirements": [
                            "Project decisive_evidence into an explicit visible candidate ledger before any scoring.",
                            "Preserve candidate_change_surface as a plausible distractor.",
                            "Emit at least one verifier/test-constraint-positive row and one candidate-surface-positive counterexample when possible.",
                            "Keep this root out of promotable strict eval until sibling/train split assignment is frozen.",
                        ],
                        "anti_cheat_requirements": [
                            "Exclude exhausted repo families from the same promotable slice.",
                            "No raw target path string visible before options.",
                            "Deterministic or recorded option shuffle required.",
                            "Require human-judgeable visible evidence and selected-test anchor exposure for promotable rows.",
                        ],
                        "why_now": (
                            "Current evidence bottleneck is flat on repository_library/parametergolf/tokenizers/candle; "
                            "this root provides fresh-family verifier-target supply."
                        ),
                    }
                )
                priority += 1

    blocked_ready_bundles = [
        row for row in ready_bundles
        if str(row.get("language_family") or "") == "web_js_ts_html"
        and not list(row.get("selected_tests") or [])
    ]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(queue_rows),
        "decision": "fresh_family_evidence_queue_prepared",
        "claim_scope": [
            "Prepare a fresh-family evidence materialization queue outside the exhausted residual repo families.",
            "Bias the next promotable evidence-lane attempt toward new root families with verifier-target signal instead of more same-family reuse.",
            "Attach anti-cheat and heldout-split requirements at queue time so fresh rows do not silently become another contaminated support loop.",
        ],
        "source_artifacts": {
            "top_seed_rows": rel(TOP_SEEDS),
            "root_records": rel(ROOT_RECORDS),
            "causal_states": rel(CAUSAL_STATES),
            "multitarget_rows": rel(MULTITARGET_ROWS),
            "ready_bundles": rel(READY_BUNDLES),
        },
        "metrics": {
            "queued_roots": len(queue_rows),
            "queued_by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in queue_rows).items())),
            "queued_by_repo_family": dict(sorted(Counter(str(row.get("repo_family") or "") for row in queue_rows).items())),
            "family_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in family_rows).items())),
            "blocked_ready_web_bundles_without_selected_tests": len(blocked_ready_bundles),
        },
        "findings": [
            "Fresh compiled roots with verifier-target signal already exist in faiss, diffusers, django, openai-agents-python, onnxruntime, cccl, and mem0.",
            "The next promotable evidence attempt should stop centering repository_library, parametergolf, tokenizers, and candle as the main residual bank.",
            "Web still has reviewed bundles without selected tests, so mem0 is the cleanest current pure-web fresh-family queue candidate.",
        ],
        "next_best_step": [
            "Materialize at least one Python row each from faiss/diffusers/django/openai-agents-python.",
            "Materialize at least one C/C++ row each from onnxruntime and cccl before another promotable evidence probe.",
            "Materialize a pure-web mem0 row with explicit selected-test/verifier ledger before broadening web claims.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "queue_rows_jsonl": rel(QUEUE_ROWS_JSONL),
            "family_atlas_jsonl": rel(FAMILY_ATLAS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(QUEUE_ROWS_JSONL, queue_rows)
    write_jsonl(FAMILY_ATLAS_JSONL, family_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
