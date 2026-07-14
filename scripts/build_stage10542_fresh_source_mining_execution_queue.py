#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

STAGE = 10542
NAME = "stage10542_fresh_source_mining_execution_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
QUEUE_JSON = OUT_DIR / "fresh_source_mining_execution_queue.json"

REQUEST = ROOT / "runs/local/artifacts/stage10540_fresh_source_multilingual_root_mining_request/fresh_source_multilingual_root_mining_request.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    request = load_json(REQUEST)

    queue = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Execution-ready queue for the fresh-source multilingual root mining stage.",
            "Provides concrete command templates and output locations for Python/C++, Rust, and web source mining/materialization.",
            "This is a mining execution plan artifact, not a model-quality result.",
        ],
        "source_request": str(REQUEST.relative_to(ROOT)),
        "queue": [
            {
                "priority": 1,
                "name": "python_cpp_local_session_episode_mining",
                "goal": "Mine fresh local session episodes with selected tests and verification targets for Python and C/C++ patch/action heldout growth.",
                "command_template": [
                    "python",
                    "scripts/mine_local_root_session_episodes.py",
                    "--repo-root",
                    "<LOCAL_REPO_ROOT>",
                    "--output-dir",
                    "runs/local/artifacts/stage10540_python_cpp_local_session_mining",
                ],
                "expected_outputs": [
                    "episode rows with selected tests",
                    "verification-backed task summaries",
                    "fresh Python/C++ root candidates",
                ],
            },
            {
                "priority": 2,
                "name": "session_seed_candidate_build",
                "goal": "Build verification-backed session seed candidates from normalized event traces for local/session source lanes.",
                "command_template": [
                    "python",
                    "scripts/build_session_episode_seed_candidates.py",
                    "--normalized-events",
                    "<NORMALIZED_EVENTS_JSONL>",
                    "--execution-traces",
                    "<EXECUTION_TRACES_JSONL>",
                    "--require-execution-traces",
                    "--output-dir",
                    "runs/local/artifacts/stage10540_session_seed_candidates",
                ],
                "expected_outputs": [
                    "session_episode_seed_candidates.jsonl",
                    "session_episode_seed_summary.json",
                ],
            },
            {
                "priority": 3,
                "name": "rust_true_source_bundle_conversion",
                "goal": "Convert the stage10125 Rust discovery manifest into fresh maintainer-visible root bundles, emphasizing non-tokenizers families.",
                "source_artifact": "runs/local/artifacts/stage10125_true_source_backed_rust_root_discovery_manifest/true_source_backed_rust_root_discovery_manifest.json",
                "recommended_candidates": [
                    "candle::candle-core",
                    "candle::candle-nn",
                    "candle::candle-examples",
                    "git::contrib/libgit-rs",
                    "git::contrib/libgit-sys",
                    "LLaMA-Adapter::gorilla",
                ],
                "gates": [
                    "tokenizers same-surface rows remain diagnostic-only",
                    "at least 4 non-tokenizers fresh roots",
                    "selected tests or equivalent verifier anchors present",
                ],
            },
            {
                "priority": 4,
                "name": "external_repo_seed_mining_for_web_and_rust",
                "goal": "Mine fresh external repo commit seeds for new web repos and additional Rust repos when current session inventory is exhausted.",
                "command_template": [
                    "python",
                    "scripts/mine_external_repo_commit_episode_seeds.py",
                    "--repo-root",
                    "<EXTERNAL_REPO_ROOT>",
                    "--output",
                    "runs/local/artifacts/stage10540_external_repo_commit_seeds/external_repo_commit_episode_seeds.jsonl",
                    "--summary-output",
                    "runs/local/artifacts/stage10540_external_repo_commit_seeds/external_repo_commit_episode_seed_summary.json",
                    "--max-repos",
                    "64",
                    "--max-commits-per-repo",
                    "3",
                    "--max-files-per-commit",
                    "6",
                ],
                "expected_outputs": [
                    "fresh web repo seeds from new repo families",
                    "additional Rust repo seeds beyond the current discovery manifest",
                ],
            },
            {
                "priority": 5,
                "name": "fresh_web_candidate_atlas_rerun",
                "goal": "Rerun the web candidate atlas only after new source/session inventories arrive.",
                "source_constraint": "Current default atlas is exhausted; do not rerun on the same inventory.",
                "command_template": [
                    "python",
                    "scripts/build_stage10262_fresh_web_root_candidate_atlas.py",
                ],
                "expected_outputs": [
                    "nonzero fresh web candidates from at least 2 new repo families",
                ],
            },
        ],
        "completion_gates": request["global_gates"],
        "minimum_outputs": request["global_minimum_outputs"],
        "next_best_step": (
            "Use the queued miners/builders to materialize fresh multilingual roots immediately after the stage10532 comparison lands, "
            "then compile the post-stage10531 expansion manifest."
        ),
    }

    write_json(QUEUE_JSON, queue)
    write_json(SUMMARY, queue)


if __name__ == "__main__":
    main()
