#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
OUT_DIR = ARTIFACTS / "stage11026_multilingual_fresh_source_acquisition_atlas"

SCALING_ATLAS = ARTIFACTS / "stage10417_multilingual_reviewed_scaling_atlas" / "multilingual_reviewed_scaling_atlas.json"
ROOT_PREVIEW = ARTIFACTS / "stage10119_true_source_backed_maintainer_root_bundle_preview" / "true_source_backed_maintainer_root_bundle_preview.jsonl"
RUST_PREVIEW = ARTIFACTS / "stage10126_true_source_backed_rust_root_bundle_preview" / "true_source_backed_rust_root_bundle_preview.jsonl"
LONG_CONTEXT_ROOTS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_root_records.jsonl"
EXPANSION_QUEUE = ARTIFACTS / "stage11025_fresh_evidence_root_expansion_queue" / "fresh_evidence_root_expansion_queue.json"

CURRENT_REPO_FAMILIES = {"repository_library", "parametergolf", "agentkernel", "candle", "tokenizers", "code_assist"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    scaling = read_json(SCALING_ATLAS)
    root_preview = read_jsonl(ROOT_PREVIEW)
    rust_preview = read_jsonl(RUST_PREVIEW)
    long_context_roots = read_jsonl(LONG_CONTEXT_ROOTS)
    expansion_queue = read_json(EXPANSION_QUEUE)

    admitted_rows = scaling.get("admitted_bundle_rows", [])
    ready_bundle_rows: list[dict] = []
    for row in admitted_rows:
        lang = row.get("language_family")
        if lang not in {"python", "c_cpp", "web_js_ts_html"}:
            continue
        ready_bundle_rows.append(
            {
                "kind": "reviewed_admitted_bundle",
                "bundle_id": row.get("bundle_id"),
                "language_family": lang,
                "repo_id": row.get("repo_id"),
                "selected_tests_count": row.get("selected_tests_count", 0),
                "selected_tests": row.get("selected_tests", []),
                "candidate_paths_count": row.get("candidate_paths_count", 0),
                "visible_evidence_keys": row.get("visible_evidence_keys", []),
                "non_abstention_count": row.get("non_abstention_count", 0),
                "abstention_count": row.get("abstention_count", 0),
                "admissible_for_same_surface_comparison": row.get("admissible_for_same_surface_comparison"),
                "notes": "ready_reviewed_bundle" if row.get("selected_tests_count", 0) > 0 else "needs_selected_test_anchor_for_headline_use",
            }
        )

    preview_rows: list[dict] = []
    for row in root_preview + rust_preview:
        lang = row.get("language_family")
        if lang not in {"python", "c_cpp", "web_js_ts_html"}:
            continue
        preview_rows.append(
            {
                "kind": "bundle_preview",
                "bundle_id": row.get("bundle_id"),
                "language_family": lang,
                "repo_id": row.get("repo_id"),
                "selected_tests_count": len(row.get("selected_tests") or []),
                "selected_tests": row.get("selected_tests") or [],
                "candidate_paths_count": len(row.get("candidate_paths") or []),
                "candidate_paths": row.get("candidate_paths") or [],
            }
        )

    seed_counts = Counter()
    for row in long_context_roots:
        lang = row.get("language_family")
        repo_family = row.get("repo_family")
        if lang not in {"python", "c_cpp", "web_js_ts_html"}:
            continue
        if not repo_family or repo_family in CURRENT_REPO_FAMILIES:
            continue
        seed_counts[(lang, repo_family)] += 1

    long_context_seeds: list[dict] = []
    for (lang, repo_family), count in seed_counts.most_common():
        long_context_seeds.append(
            {
                "kind": "long_context_seed_family",
                "language_family": lang,
                "repo_family": repo_family,
                "compiled_root_count": count,
            }
        )

    top_seed_rows: list[dict] = []
    wanted_per_lang = {"python": 8, "c_cpp": 6, "web_js_ts_html": 6}
    taken = defaultdict(int)
    for row in long_context_seeds:
        lang = row["language_family"]
        if taken[lang] >= wanted_per_lang[lang]:
            continue
        top_seed_rows.append(row)
        taken[lang] += 1

    prioritized_actions = [
        {
            "priority": 1,
            "language_family": "python",
            "action": "materialize_new_fresh_evidence_roots",
            "targets": [
                "stage10119::localsess_repository_library...::python (MirrorMind verifier/test family)",
                "new long-context seed families with selected-test mining from faiss, diffusers, django, openai-agents-python"
            ],
            "why": "Python still has only one fresh evidence candidate root in the current candidate bank and one remaining strict verifier miss."
        },
        {
            "priority": 2,
            "language_family": "c_cpp",
            "action": "materialize_new_fresh_evidence_roots",
            "targets": [
                "stage10119::localsess_agentkernel...::c_cpp",
                "stage10119::localsess_parametergolf...::c_cpp",
                "new long-context seed families from onnxruntime and cccl"
            ],
            "why": "C/C++ fresh evidence currently relies on two roots plus same-root geometry variants."
        },
        {
            "priority": 3,
            "language_family": "web_js_ts_html",
            "action": "acquire_pure_web_selected_test_family",
            "targets": [
                "promote a non-overlap web bundle with selected tests beyond code_assist",
                "mine mem0 and bddy_website source families for selected-test anchors"
            ],
            "why": "Web still has no promotable fresh evidence root with a clean selected-test anchor."
        },
    ]

    summary = {
        "stage": 11026,
        "stage_name": "multilingual_fresh_source_acquisition_atlas",
        "claim_scope": [
            "Identify concrete next Python/C++/web source families for fresh evidence-root expansion.",
            "Separate already reviewed bundle roots from long-context seed families that still need selected-test and maintainer-grade materialization.",
            "Provide a direct bridge from the current narrow evidence queue to larger honest multilingual root supply."
        ],
        "source_artifacts": {
            "reviewed_scaling_atlas": str(SCALING_ATLAS.relative_to(ROOT)),
            "true_source_preview": str(ROOT_PREVIEW.relative_to(ROOT)),
            "rust_preview": str(RUST_PREVIEW.relative_to(ROOT)),
            "long_context_root_records": str(LONG_CONTEXT_ROOTS.relative_to(ROOT)),
            "expansion_queue": str(EXPANSION_QUEUE.relative_to(ROOT)),
        },
        "metrics": {
            "current_queue_summary": expansion_queue["metrics"],
            "ready_bundle_rows": len(ready_bundle_rows),
            "ready_bundle_by_language": dict(Counter(row["language_family"] for row in ready_bundle_rows)),
            "preview_rows": len(preview_rows),
            "preview_by_language": dict(Counter(row["language_family"] for row in preview_rows)),
            "long_context_seed_families_total": len(long_context_seeds),
            "long_context_seed_top_by_language": dict(Counter(row["language_family"] for row in top_seed_rows)),
        },
        "findings": [
            "There are already reviewed Python/C++ bundle roots with selected tests beyond the immediate evidence queue, especially the Python MirrorMind family and the admitted C/C++ bundles.",
            "Web has reviewed bundles, but the cleanest current non-overlap reviewed web bundles still lack selected tests; code_assist has selected tests but remains overlap-sensitive.",
            "The compiled long-context root inventory exposes many additional Python and C/C++ repo families that can feed the next scale stage once selected-test and anti-cheat materialization is added."
        ],
        "next_best_step": prioritized_actions,
        "outputs": {
            "summary_json": str((OUT_DIR / "multilingual_fresh_source_acquisition_atlas.json").relative_to(ROOT)),
            "ready_bundle_rows_jsonl": str((OUT_DIR / "ready_bundle_rows.jsonl").relative_to(ROOT)),
            "preview_rows_jsonl": str((OUT_DIR / "preview_rows.jsonl").relative_to(ROOT)),
            "top_seed_rows_jsonl": str((OUT_DIR / "top_seed_rows.jsonl").relative_to(ROOT)),
        },
        "passed": True,
    }

    write_jsonl(OUT_DIR / "ready_bundle_rows.jsonl", ready_bundle_rows)
    write_jsonl(OUT_DIR / "preview_rows.jsonl", preview_rows)
    write_jsonl(OUT_DIR / "top_seed_rows.jsonl", top_seed_rows)
    (OUT_DIR / "multilingual_fresh_source_acquisition_atlas.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
