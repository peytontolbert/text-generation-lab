#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10885
NAME = "stage10885_tokenizers_bindings_node_preview"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "tokenizers_bindings_node_preview.json"
BUNDLE_JSON = OUT_DIR / "tokenizers_bindings_node_preview_bundle.json"

TRAIN_PACKAGE = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package" / "agentkernel_lite_encdec_train.jsonl"
ATLAS_JSON = ARTIFACTS / "stage10411_fresh_rust_disjoint_root_candidate_atlas" / "fresh_rust_disjoint_root_candidate_atlas.json"
SUPPLY_JSON = ARTIFACTS / "stage10822_residual_lane_fresh_root_supply_manifest" / "residual_lane_fresh_root_supply_manifest.json"
SESSION_TRACES = ARTIFACTS / "session_like_source_inventory_real" / "current_recent96_session_execution_traces" / "session_execution_traces.jsonl"

TOKENIZERS_ROOT = Path("/arxiv/repositories/tokenizers")
CANDIDATE_ROOT_ID = "tokenizers::bindings/node"
MAX_TEXT = 1200
PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "patch_impact",
    "verifier_outcome",
    "minimal_fix_selection",
    "regression_risk",
    "abstention_insufficient_evidence",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact(text: str, limit: int = MAX_TEXT) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def read_file(rel_path: str) -> str:
    return compact((TOKENIZERS_ROOT / rel_path).read_text(encoding="utf-8", errors="replace"))


def candidate_record() -> dict[str, Any]:
    atlas = load_json(ATLAS_JSON)
    for row in atlas.get("top_fresh_candidates") or []:
        if str(row.get("candidate_root_id") or "") == CANDIDATE_ROOT_ID:
            return row
    raise KeyError(f"missing candidate root {CANDIDATE_ROOT_ID}")


def trace_snippets() -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for row in load_jsonl(SESSION_TRACES):
        refs = row.get("file_path_refs") or []
        if "bindings/node/Cargo.toml" not in refs:
            continue
        cmd = str(row.get("command") or "")
        if "cargo check" not in cmd and "Cargo.toml" not in cmd and "stage5418" not in cmd:
            continue
        hits.append(
            {
                "command": compact(cmd, limit=420),
                "summary_text": compact(str(row.get("summary_text") or ""), limit=620),
                "failure_type": str(((row.get("runtime_trace") or {}).get("failure_type")) or "unknown"),
                "refs": refs[:10],
            }
        )
        if len(hits) >= 3:
            break
    return hits


def perspective_row(bundle_id: str, perspective: str, evidence: dict[str, list[dict[str, Any]]], candidate_paths: list[str], selected_tests: list[str]) -> dict[str, Any]:
    tasks = {
        "symptom_localization": "Choose the most plausible bindings-node surface to inspect or edit from the visible source and build evidence.",
        "evidence_citation": "Name the visible fact that best supports the chosen bindings-node edit target.",
        "alternative_hypothesis_elimination": "Explain why a plausible alternative bindings-node surface is less justified.",
        "patch_impact": "Compare candidate bindings-node edits by likely behavior change and risk.",
        "verifier_outcome": "Predict which visible build or verifier target should change if the fix is correct.",
        "minimal_fix_selection": "Choose the smallest maintainable bindings-node intervention supported by the evidence.",
        "regression_risk": "Identify what the likely bindings-node fix might break or destabilize.",
        "abstention_insufficient_evidence": "Decide whether the visible bindings-node evidence is sufficient for a singleton answer or whether abstention is more honest.",
    }
    return {
        "bundle_id": bundle_id,
        "language_family": "rust",
        "perspective": perspective,
        "prompt_contract": {
            "task": tasks[perspective],
            "candidate_paths": candidate_paths,
            "selected_tests": selected_tests,
            "visible_evidence_keys": sorted(key for key, value in evidence.items() if value),
            "abstention_option_required": perspective == "abstention_insufficient_evidence",
        },
        "gold_answer_status": "ai_or_human_adjudication_required",
        "eligible_for_training_or_scoring_now": False,
    }


def main() -> None:
    candidate = candidate_record()
    traces = trace_snippets()
    train_roots = {
        str(row.get("source_bundle_id") or row.get("source_root_id") or "")
        for row in load_jsonl(TRAIN_PACKAGE)
    }

    candidate_paths = [
        "bindings/node/build.rs",
        "bindings/node/src/tokenizer.rs",
        "bindings/node/src/pre_tokenizers.rs",
        "bindings/node/src/models.rs",
        "bindings/node/src/tasks/tokenizer.rs",
    ]
    selected_tests = ["cargo check --manifest-path bindings/node/Cargo.toml --offline --quiet"]
    bundle_id = "stage10885::tokenizers::bindings-node::rust"

    evidence = {
        "algorithmic_background_reference": [
            {
                "path": "bindings/node/build.rs",
                "source_type": "external_repo_source_file",
                "retrieval_reason": "bindings_node_build_background",
                "distance_from_seed": 0,
                "text": read_file("bindings/node/build.rs"),
                "meta": {"repo": "tokenizers", "kind": "code"},
            }
        ],
        "candidate_change_surface": [
            {
                "path": "bindings/node/src/tokenizer.rs",
                "source_type": "external_repo_source_file",
                "retrieval_reason": "bindings_node_candidate_surface",
                "distance_from_seed": 0,
                "text": read_file("bindings/node/src/tokenizer.rs"),
                "meta": {"repo": "tokenizers", "kind": "code"},
            }
        ],
        "nearby_definition_or_usage_context": [
            {
                "path": "bindings/node/src/models.rs",
                "source_type": "external_repo_source_file",
                "retrieval_reason": "bindings_node_nearby_model_context",
                "distance_from_seed": 0,
                "text": read_file("bindings/node/src/models.rs"),
                "meta": {"repo": "tokenizers", "kind": "code"},
            },
            {
                "path": "bindings/node/src/pre_tokenizers.rs",
                "source_type": "external_repo_source_file",
                "retrieval_reason": "bindings_node_nearby_pretokenizer_context",
                "distance_from_seed": 0,
                "text": read_file("bindings/node/src/pre_tokenizers.rs"),
                "meta": {"repo": "tokenizers", "kind": "code"},
            },
        ],
        "symptom_or_call_path_analogue": [
            {
                "path": "bindings/node/src/tasks/tokenizer.rs",
                "source_type": "external_repo_source_file",
                "retrieval_reason": "bindings_node_encode_decode_task_flow",
                "distance_from_seed": 0,
                "text": read_file("bindings/node/src/tasks/tokenizer.rs"),
                "meta": {"repo": "tokenizers", "kind": "code"},
            }
        ],
        "verifier_and_test_constraint": [
            {
                "path": "bindings/node/Cargo.toml",
                "source_type": "external_repo_source_file",
                "retrieval_reason": "bindings_node_manifest_build_constraint",
                "distance_from_seed": 0,
                "text": read_file("bindings/node/Cargo.toml"),
                "meta": {"repo": "tokenizers", "kind": "manifest"},
            },
            *[
                {
                    "path": "bindings/node/Cargo.toml",
                    "source_type": "session_trace_summary",
                    "retrieval_reason": "bindings_node_local_cargo_check_trace",
                    "distance_from_seed": 0,
                    "text": item["summary_text"],
                    "meta": {
                        "repo": "agentkernel-seq2seq-text-lab",
                        "kind": "session_trace",
                        "command": item["command"],
                        "failure_type": item["failure_type"],
                    },
                }
                for item in traces
            ],
        ],
    }

    bundle = {
        "bundle_id": bundle_id,
        "root_example_id": CANDIDATE_ROOT_ID,
        "repo_id": "tokenizers",
        "language_family": "rust",
        "source_route": "external_repo_source_plus_local_session_trace",
        "seed_paths": candidate_paths,
        "selected_tests": selected_tests,
        "claim_boundary": {
            "gold_answers_fully_adjudicated": False,
            "supports_training_or_scoring_now": False,
            "preview_only": True,
            "build_anchored_not_test_anchored": True,
            "root_disjoint_from_current_train_package": CANDIDATE_ROOT_ID not in train_roots,
        },
        "maintainer_visible_evidence": evidence,
        "candidate_paths": candidate_paths,
        "discovery_metadata": {
            "package_root": candidate["package_root"],
            "richness_score": candidate["richness_score"],
            "competition_geometries": candidate["competition_geometries"],
            "review_ready_for_bundle_construction": candidate["review_ready_for_bundle_construction"],
            "test_file_count": candidate["test_file_count"],
            "build_file_count": candidate["build_file_count"],
            "local_trace_anchor_count": len(traces),
        },
        "perspective_rows": [
            perspective_row(bundle_id, perspective, evidence, candidate_paths, selected_tests)
            for perspective in PERSPECTIVES
        ],
        "local_trace_anchor_examples": traces,
    }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "tokenizers_bindings_node_preview_materialized",
        "claim_scope": [
            "Materialize the highest-priority root-disjoint Rust candidate, tokenizers::bindings/node, into a concrete maintainer-bundle preview.",
            "Show whether current local source and session-trace evidence are sufficient to move it from queue suggestion to adjudication-ready preview.",
        ],
        "metrics": {
            "root_disjoint_from_current_train_package": CANDIDATE_ROOT_ID not in train_roots,
            "candidate_paths_count": len(candidate_paths),
            "selected_build_anchor_count": len(selected_tests),
            "local_trace_anchor_count": len(traces),
            "visible_evidence_keys": sorted(k for k, v in evidence.items() if v),
        },
        "interpretation": [
            "bindings/node is now a concrete preview bundle rather than just an atlas candidate.",
            "It has real source-backed candidate surfaces plus a build-verifier anchor from Cargo.toml and local cargo-check trace summaries.",
            "It is still not scoreable until gold adjudication and anti-cheat review decide whether the build anchor is strong enough for maintainer-grade evidence-citation and verifier rows.",
        ],
        "remaining_gates": [
            "ai_or_human_gold_adjudication_for_all_8_perspectives",
            "anti_cheat_review_of_build_anchor_and_path_bias",
            "decision_on_whether_build-anchored verifier is promotable or train-support-only",
        ],
        "next_best_step": "Run an AI adjudication pass over this preview bundle and decide whether it can serve as a root-disjoint Rust heldout replenishment packet or only as support/stress material.",
        "source_artifacts": {
            "atlas": rel(ATLAS_JSON),
            "supply_manifest": rel(SUPPLY_JSON),
            "train_package": rel(TRAIN_PACKAGE),
        },
        "outputs": {
            "bundle_json": rel(BUNDLE_JSON),
            "summary_json": rel(SUMMARY_JSON),
        },
    }

    write_json(BUNDLE_JSON, bundle)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
