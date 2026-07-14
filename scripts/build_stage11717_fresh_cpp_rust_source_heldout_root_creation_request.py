#!/usr/bin/env python3
"""Create fresh C/C++ and Rust source-heldout root creation requests.

Stage11716 showed existing artifacts cannot provide C/C++ or Rust source-heldout
smoke candidates after train/source-file exclusion. This stage inventories local
source repos and emits fresh-root creation requests that must carry source-heldout
attestation at creation time.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11717_fresh_cpp_rust_source_heldout_root_creation_request"
SUMMARY = ROOT / "runs/summaries/stage11717_fresh_cpp_rust_source_heldout_root_creation_request.json"
HELPFUL = Path("/data/parametergolf/helpful_repos")
STAGE11716 = ROOT / "runs/local/artifacts/stage11716_train_excluded_source_heldout_smoke_miner/train_excluded_source_heldout_smoke_miner.json"
PRIOR = {
    "cpp_queue": ROOT / "runs/local/artifacts/stage10740_cpp_bulk_materialization_queue/cpp_bulk_materialization_queue.json",
    "rust_inventory": ROOT / "runs/local/artifacts/stage10664_rust_materialization_inventory_refresh/rust_materialization_inventory_refresh.json",
    "rust_atlas": ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json",
}

CPP_EXTS = ("*.cpp", "*.cc", "*.c", "*.h", "*.hpp", "*.cu")
RUST_EXTS = ("*.rs",)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def git_commit(path: Path) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        return None
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None


def count_globs(path: Path, patterns: tuple[str, ...]) -> int:
    total = 0
    for pat in patterns:
        try:
            total += sum(1 for _ in path.rglob(pat))
        except OSError:
            pass
    return total


def sample_files(path: Path, patterns: tuple[str, ...], limit: int = 12) -> list[str]:
    files: list[str] = []
    for pat in patterns:
        for p in sorted(path.rglob(pat)):
            if any(part in {".git", "build", "dist", "target", "__pycache__"} for part in p.parts):
                continue
            files.append(str(p.relative_to(path)))
            if len(files) >= limit:
                return files
    return files


def repo_card(path: Path) -> dict[str, Any]:
    markers = [name for name in ["Cargo.toml", "CMakeLists.txt", "Makefile", "meson.build", "setup.py", "pyproject.toml"] if (path / name).exists()]
    cpp_count = count_globs(path, CPP_EXTS)
    rust_count = count_globs(path, RUST_EXTS)
    return {
        "repo_name": path.name,
        "path": str(path),
        "commit": git_commit(path),
        "markers": markers,
        "cpp_file_count": cpp_count,
        "rust_file_count": rust_count,
        "cpp_samples": sample_files(path, CPP_EXTS, 10),
        "rust_samples": sample_files(path, RUST_EXTS, 10),
    }


def inventory_local_repos() -> list[dict[str, Any]]:
    if not HELPFUL.exists():
        return []
    cards = []
    for path in sorted(p for p in HELPFUL.iterdir() if p.is_dir()):
        card = repo_card(path)
        if card["cpp_file_count"] or card["rust_file_count"]:
            cards.append(card)
    return cards


def choose_cpp(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred = ["sentencepiece", "bitsandbytes", "mamba", "statespace_101", "model-stack", "pytorch", "faiss"]
    by_name = {c["repo_name"]: c for c in cards if c["cpp_file_count"]}
    selected = [by_name[name] for name in preferred if name in by_name]
    selected += [c for c in sorted(by_name.values(), key=lambda x: x["cpp_file_count"], reverse=True) if c not in selected]
    return selected[:6]


def choose_rust(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred = ["tokenizers"]
    by_name = {c["repo_name"]: c for c in cards if c["rust_file_count"]}
    selected = [by_name[name] for name in preferred if name in by_name]
    selected += [c for c in sorted(by_name.values(), key=lambda x: x["rust_file_count"], reverse=True) if c not in selected]
    return selected[:4]


def request(repo: dict[str, Any], language_family: str, priority: int) -> dict[str, Any]:
    samples = repo["rust_samples"] if language_family == "rust" else repo["cpp_samples"]
    return {
        "request_type": "fresh_source_heldout_root_creation",
        "priority": priority,
        "language_family": language_family,
        "repo_family": repo["repo_name"],
        "repo_path": repo["path"],
        "repo_commit": repo["commit"],
        "source_snapshot_id": f"{repo['repo_name']}::{repo['commit'] or 'unversioned'}",
        "markers": repo["markers"],
        "source_file_count": repo["rust_file_count"] if language_family == "rust" else repo["cpp_file_count"],
        "sample_source_paths": samples,
        "root_creation_requirements": [
            "create new root_id/root_lineage_key at materialization time",
            "assert source_heldout_admissible=true only after no train/support overlap scan passes",
            "train_eligible=false for strict smoke rows",
            "persist exact repo path and commit/snapshot hash",
            "store concrete source snippets and candidate paths",
            "store selected_test_anchor or verifier_anchor with observable command/log when available",
            "set deterministic_option_shuffle=true with persisted opaque option order",
            "run prompt target-label/value leak audit before admission",
        ],
        "minimum_perspectives": [
            "symptom_localization",
            "evidence_citation",
            "verifier_outcome_or_abstain",
            "patch_impact_or_abstain",
        ],
        "full_product_extension_requirements": [
            "patch_or_abstain candidate row",
            "harness_run_id",
            "same_task_pack_as_gemma12b=true",
            "tool_trace_spans",
            "verifier_results",
            "patch_minimality_or_abstain_scores",
        ],
        "anti_cheat_requirements": [
            "no singleton options",
            "no target path/value visible before options unless every candidate is equally visible",
            "candidate order permutation audit",
            "root/repo/time split proof",
            "no row derived from prior train/support root",
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    cards = inventory_local_repos()
    cpp = choose_cpp(cards)
    rust = choose_rust(cards)
    stage11716 = read_json(STAGE11716) if STAGE11716.exists() else {}
    prior = {name: read_json(path) for name, path in PRIOR.items() if path.exists()}
    requests = [request(repo, "c_cpp", i + 1) for i, repo in enumerate(cpp)]
    requests += [request(repo, "rust", i + 1) for i, repo in enumerate(rust)]
    counts = Counter(r["language_family"] for r in requests)
    passed = counts.get("c_cpp", 0) > 0 and counts.get("rust", 0) > 0
    artifact = {
        "stage": 11717,
        "stage_name": "fresh_cpp_rust_source_heldout_root_creation_request",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "fresh_cpp_rust_root_creation_requests_ready" if passed else "fresh_cpp_rust_root_creation_requests_insufficient",
        "passed": passed,
        "why_needed": [
            "Stage11716 found zero C/C++ and zero Rust source-heldout smoke candidates after train/source-file exclusion.",
            "Existing C/C++ and Rust artifact lanes are mostly train-support/materialization queues, not strict source-heldout smoke rows.",
            "Fresh roots must carry source-heldout lineage, verifier/test anchors, and anti-cheat fields at creation time.",
        ],
        "local_repo_inventory": {
            "repo_count_with_cpp_or_rust": len(cards),
            "cpp_candidate_repos": [c["repo_name"] for c in cpp],
            "rust_candidate_repos": [c["repo_name"] for c in rust],
        },
        "request_counts": dict(counts),
        "selected_requests_preview": [
            {
                "language_family": r["language_family"],
                "repo_family": r["repo_family"],
                "source_file_count": r["source_file_count"],
                "sample_source_paths": r["sample_source_paths"][:5],
            }
            for r in requests
        ],
        "stage11716_context": {
            "decision": stage11716.get("decision"),
            "selected_root_counts": stage11716.get("selected_root_counts"),
            "mine_summary": stage11716.get("mine_summary"),
        },
        "prior_artifact_context": prior,
        "claim_boundary": [
            "This is a fresh-root creation request, not an admission or model scoring stage.",
            "Local source availability does not prove source-heldout status; final rows need a no-train overlap audit after materialization.",
            "No broad C/C++ or Rust source-heldout claim should be made until at least one root per language passes admission and same-manifest 100M/Gemma scoring.",
        ],
        "next_stage_acceptance": [
            "materialize at least one C/C++ and one Rust root from these requests",
            "attach root_lineage_key/source snapshot and no train/support overlap proof",
            "attach verifier/test anchor or explicit abstain reason",
            "emit Stage11714-style preflight with no standalone blockers",
        ],
        "source_artifacts": {
            "stage11716": str(STAGE11716.relative_to(ROOT)) if STAGE11716.exists() else None,
            "helpful_repos": str(HELPFUL),
        },
        "outputs": {
            "artifact": "runs/local/artifacts/stage11717_fresh_cpp_rust_source_heldout_root_creation_request/fresh_cpp_rust_source_heldout_root_creation_request.json",
            "requests_jsonl": "runs/local/artifacts/stage11717_fresh_cpp_rust_source_heldout_root_creation_request/fresh_cpp_rust_source_heldout_root_creation_requests.jsonl",
            "repo_inventory_jsonl": "runs/local/artifacts/stage11717_fresh_cpp_rust_source_heldout_root_creation_request/local_cpp_rust_repo_inventory.jsonl",
            "summary": "runs/summaries/stage11717_fresh_cpp_rust_source_heldout_root_creation_request.json",
        },
    }
    artifact_path = OUT_DIR / "fresh_cpp_rust_source_heldout_root_creation_request.json"
    req_path = OUT_DIR / "fresh_cpp_rust_source_heldout_root_creation_requests.jsonl"
    inv_path = OUT_DIR / "local_cpp_rust_repo_inventory.jsonl"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with req_path.open("w", encoding="utf-8") as fh:
        for req in requests:
            fh.write(json.dumps(req, sort_keys=True) + "\n")
    with inv_path.open("w", encoding="utf-8") as fh:
        for card in cards:
            fh.write(json.dumps(card, sort_keys=True) + "\n")
    shutil.copyfile(artifact_path, SUMMARY)
    print(json.dumps({"artifact": str(artifact_path), "summary": str(SUMMARY), "passed": passed, "request_counts": dict(counts)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
