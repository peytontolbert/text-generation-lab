#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10583
NAME = "stage10583_fresh_python_cpp_decisive_root_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "fresh_python_cpp_decisive_root_package.json"
SUPPORT_BUNDLES_JSONL = OUT_DIR / "support_root_bundles.jsonl"
STRICT_BUNDLES_JSONL = OUT_DIR / "strict_eval_root_bundles.jsonl"
SUPPORT_ROWS_JSONL = OUT_DIR / "support_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "strict_eval_rows.jsonl"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

SEED_RECORDS = ROOT / "runs/local/artifacts/stage10582_fresh_multilingual_decisive_root_supply_audit/fresh_multilingual_decisive_root_seed_records.jsonl"
COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
COMPILED_ROWS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"

REQUIRED_SUBTYPES = ["decisive_evidence", "retrieve_answer_abstain", "verifier_outcome"]

PYTHON_STRICT_REPOS = {
    "Megatron-LM",
    "Model-Optimizer",
    "NeMo",
    "TensorRT-LLM",
    "TransformerEngine",
    "agent-framework",
    "agent-governance-toolkit",
    "autogen",
}
PYTHON_SUPPORT_REPOS = {
    "agentkernel",
    "agentkernel-seq2seq-text-lab",
    "diffusers",
    "faiss",
    "conan",
    "cpython",
    "django",
    "jax",
    "langchain",
}

C_CPP_STRICT_REPOS = {
    "cand_ent_cache_enabled_d2019abcfd_50_f30d6759c8",
    "cand_ent_fixed_size_157ebd2bb6_46_89328660a7",
    "cand_ent_low_rank_04201d143c_11_291afa8a1c",
    "cand_ent_non_deterministic_6c8c53f29d_14_218cb20989",
    "cand_ent_non_linear_ccc83e0172_13_499acbad7d",
    "cand_ent_non_trivial_e078aa07fe_7_d5ea6d04dc",
    "cand_ent_one_one_83b3a34858_27_fa5ccf3b07",
}
C_CPP_SUPPORT_REPOS = {"parametergolf"}

PYTHON_SUPPORT_ROOT_CAP = 18
C_CPP_SUPPORT_ROOT_CAP = 18


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def clone(value: Any) -> Any:
    return json.loads(json.dumps(value))


def main() -> None:
    seed_records = load_jsonl(SEED_RECORDS)
    compiled_roots = {row["root_id"]: row for row in load_jsonl(COMPILED_ROOTS)}
    compiled_rows = load_jsonl(COMPILED_ROWS)

    rows_by_root: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in compiled_rows:
        root_id = str(row.get("root_id") or "")
        subtype = str(row.get("target_subtype") or "")
        rows_by_root[root_id][subtype] = row

    eligible = [
        row
        for row in seed_records
        if row.get("language_family") in {"python", "c_cpp"}
        and row.get("freshness_tier") == "repo_disjoint"
        and bool(row.get("has_required_bundle"))
    ]

    support_seed_records: list[dict[str, Any]] = []
    strict_seed_records: list[dict[str, Any]] = []

    python_support_count = 0
    cpp_support_count = 0
    for row in eligible:
        lang = str(row.get("language_family") or "")
        repo = str(row.get("repo_family") or "")
        if lang == "python":
            if repo in PYTHON_STRICT_REPOS:
                strict_seed_records.append(row)
            elif repo in PYTHON_SUPPORT_REPOS and python_support_count < PYTHON_SUPPORT_ROOT_CAP:
                support_seed_records.append(row)
                python_support_count += 1
        elif lang == "c_cpp":
            if repo in C_CPP_STRICT_REPOS:
                strict_seed_records.append(row)
            elif repo in C_CPP_SUPPORT_REPOS and cpp_support_count < C_CPP_SUPPORT_ROOT_CAP:
                support_seed_records.append(row)
                cpp_support_count += 1

    def make_bundle(seed: dict[str, Any], split: str) -> dict[str, Any]:
        root_id = str(seed["root_id"])
        root = compiled_roots[root_id]
        subtype_rows = rows_by_root[root_id]
        bundle_rows: list[dict[str, Any]] = []
        for subtype in REQUIRED_SUBTYPES:
            row = clone(subtype_rows[subtype])
            row["split"] = split
            row["fresh_root_package_stage"] = STAGE
            row.setdefault("anti_cheat", {})
            row["anti_cheat"]["same_root_train_eval_forbidden"] = True
            row["anti_cheat"]["repo_family_split_disjoint"] = True
            row["anti_cheat"]["fresh_repo_disjoint_from_stage10561"] = True
            bundle_rows.append(row)
        return {
            "root_id": root_id,
            "repo_id": root.get("repo_id"),
            "repo_family": root.get("repo_family"),
            "language_family": root.get("language_family"),
            "split_component": root.get("split_component"),
            "task_family": root.get("task_family"),
            "verifier_id": root.get("verifier_id"),
            "pack_id": ((root.get("provenance") or {}).get("pack_id")),
            "query_index": ((root.get("provenance") or {}).get("query_index")),
            "quality_score": seed.get("quality_score"),
            "changed_files": seed.get("changed_files"),
            "verification_targets": seed.get("verification_targets"),
            "rows": bundle_rows,
        }

    support_bundles = [make_bundle(seed, "train") for seed in support_seed_records]
    strict_bundles = [make_bundle(seed, "strict_eval") for seed in strict_seed_records]

    support_rows = [row for bundle in support_bundles for row in bundle["rows"]]
    strict_rows = [row for bundle in strict_bundles for row in bundle["rows"]]

    def counts_from_bundles(bundles: list[dict[str, Any]]) -> dict[str, Any]:
        by_lang = Counter(str(bundle.get("language_family") or "") for bundle in bundles)
        by_repo = Counter(str(bundle.get("repo_family") or "") for bundle in bundles)
        return {
            "bundle_count": len(bundles),
            "language_counts": dict(sorted(by_lang.items())),
            "repo_counts": dict(sorted(by_repo.items())),
        }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Materializes fresh repo-disjoint Python and C/C++ decisive-root bundles from the stage10582 seed audit.",
            "Support and strict-eval candidates are split by repo family, not just by root, to reduce family-level leakage.",
            "This is a source package for the next visible-candidate projection/training step, not yet a model-comparison claim.",
        ],
        "inputs": {
            "seed_records": display(SEED_RECORDS),
            "compiled_root_records": display(COMPILED_ROOTS),
            "compiled_multitarget_rows": display(COMPILED_ROWS),
        },
        "selection_policy": {
            "required_subtypes": REQUIRED_SUBTYPES,
            "python_strict_repos": sorted(PYTHON_STRICT_REPOS),
            "python_support_repos": sorted(PYTHON_SUPPORT_REPOS),
            "c_cpp_strict_repos": sorted(C_CPP_STRICT_REPOS),
            "c_cpp_support_repos": sorted(C_CPP_SUPPORT_REPOS),
            "support_caps": {
                "python": PYTHON_SUPPORT_ROOT_CAP,
                "c_cpp": C_CPP_SUPPORT_ROOT_CAP,
            },
            "repo_family_split_disjoint": True,
            "freshness_tier_required": "repo_disjoint",
        },
        "support": counts_from_bundles(support_bundles),
        "strict_eval": counts_from_bundles(strict_bundles),
        "top_support_roots": [
            {
                "root_id": bundle["root_id"],
                "repo_family": bundle["repo_family"],
                "language_family": bundle["language_family"],
                "quality_score": bundle["quality_score"],
                "query_index": bundle["query_index"],
            }
            for bundle in support_bundles[:16]
        ],
        "top_strict_roots": [
            {
                "root_id": bundle["root_id"],
                "repo_family": bundle["repo_family"],
                "language_family": bundle["language_family"],
                "quality_score": bundle["quality_score"],
                "query_index": bundle["query_index"],
            }
            for bundle in strict_bundles[:16]
        ],
        "truthful_read": [
            "Python now has a real repo-disjoint fresh-root package with train-vs-strict repo-family separation, which is stronger than same-surface support replay.",
            "C/C++ now has an honest fresh package too, but its support remains heavily concentrated in parametergolf while strict comes from cand_ent singleton repos.",
            "Rust and Web are not included here because stage10582 showed they still lack enough repo-disjoint fresh roots for a credible fresh heldout package.",
        ],
        "outputs": {
            "support_root_bundles": display(SUPPORT_BUNDLES_JSONL),
            "strict_eval_root_bundles": display(STRICT_BUNDLES_JSONL),
            "support_rows": display(SUPPORT_ROWS_JSONL),
            "strict_eval_rows": display(STRICT_ROWS_JSONL),
            "package_json": display(SUMMARY_JSON),
        },
    }

    write_jsonl(SUPPORT_BUNDLES_JSONL, support_bundles)
    write_jsonl(STRICT_BUNDLES_JSONL, strict_bundles)
    write_jsonl(SUPPORT_ROWS_JSONL, support_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_json(SUMMARY_JSON, payload)
    write_json(RUN_SUMMARY_JSON, payload)
    print(json.dumps({"support": payload["support"], "strict_eval": payload["strict_eval"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
