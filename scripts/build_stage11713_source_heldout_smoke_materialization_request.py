#!/usr/bin/env python3
"""Request source-heldout smoke materialization for Python/C/C++/Rust.

Stage11712 identified the next hard gap: no admitted source-heldout smoke rows
for Python, C/C++, or Rust. This stage does not admit rows. It selects
near-repairable seed roots and emits concrete repair/materialization work items.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11713_source_heldout_smoke_materialization_request"
SUMMARY_PATH = ROOT / "runs/summaries/stage11713_source_heldout_smoke_materialization_request.json"

NEAR_REPAIRABLE = ROOT / (
    "runs/local/artifacts/stage11519_source_heldout_smoke_candidate_miner/"
    "near_repairable_smoke_candidates.jsonl"
)
STAGE11712 = ROOT / (
    "runs/local/artifacts/stage11712_v27_completion_gap_and_next_worklist/"
    "v27_completion_gap_and_next_worklist.json"
)

TARGET_LANGS = ("python", "c_cpp", "rust")
OPTIONAL_LANGS = ("web_js_ts_html",)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def row_root(row: dict[str, Any]) -> str:
    return row.get("source_root_id") or row.get("root_id") or row.get("row_id", "").split("::", 3)[0]


def row_score(row: dict[str, Any]) -> tuple[int, int, int, int, int, int, int, int]:
    """Higher is better; tuple keeps ordering deterministic."""
    blockers = set(row.get("blockers") or [])
    task = row.get("task_type")
    source_file = str(row.get("source_file") or "")
    trainish_source = any(token in source_file for token in ("train", "support", "probe_request"))
    return (
        8 if row.get("split") == "strict_eval" else 0,
        6 if row.get("heldout_like") is True else 0,
        0 if trainish_source else 5,
        4 if row.get("selected_test_anchor") or row.get("verifier_anchor") else 0,
        3 if "missing_verifier_or_selected_test_anchor" not in blockers else 0,
        2 if "missing_patch_or_abstain_signal" not in blockers else 0,
        2 if task in {"verifier_outcome_semantic_transition", "evidence_citation", "patch_impact"} else 1,
        int(row.get("option_count") or 0),
    )


def eligible_seed(row: dict[str, Any]) -> bool:
    blockers = set(row.get("blockers") or [])
    return (
        row.get("language_family") in TARGET_LANGS + OPTIONAL_LANGS
        and bool(row.get("source_root_id"))
        and bool(row.get("repo_family"))
        and row.get("opaque_labels") is True
        and int(row.get("option_count") or 0) >= 2
        and row.get("prompt_target_value_leak") is False
        and "singleton_or_missing_options" not in blockers
        and "prompt_target_value_leak" not in blockers
    )


def select_seed_roots(rows: list[dict[str, Any]], lang: str, max_roots: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("language_family") != lang or not eligible_seed(row):
            continue
        grouped[row_root(row)].append(row)

    candidates = []
    used_repos: set[str] = set()
    for root, root_rows in grouped.items():
        root_rows = sorted(root_rows, key=lambda r: (row_score(r), r.get("row_id", "")), reverse=True)
        best = root_rows[0]
        candidates.append(
            {
                "root_id": root,
                "repo_family": best.get("repo_family") or "unknown",
                "language_family": lang,
                "best_score": row_score(best),
                "rows": root_rows[: min(4, len(root_rows))],
            }
        )

    candidates.sort(
        key=lambda c: (
            c["best_score"],
            -len(c["rows"]),
            c["repo_family"],
            c["root_id"],
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    # First pass: maximize repo-family diversity.
    for cand in candidates:
        if len(selected) >= max_roots:
            break
        if cand["repo_family"] in used_repos:
            continue
        selected.append(cand)
        used_repos.add(cand["repo_family"])

    # Second pass: fill remaining slots with next best roots.
    selected_roots = {c["root_id"] for c in selected}
    for cand in candidates:
        if len(selected) >= max_roots:
            break
        if cand["root_id"] not in selected_roots:
            selected.append(cand)
            selected_roots.add(cand["root_id"])
    return selected


def summarize_pool(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_lang = Counter(row.get("language_family", "unknown") for row in rows)
    blockers: dict[str, Counter[str]] = defaultdict(Counter)
    repo_counts: dict[str, Counter[str]] = defaultdict(Counter)
    task_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        lang = row.get("language_family", "unknown")
        repo_counts[lang][row.get("repo_family") or "unknown"] += 1
        task_counts[lang][row.get("task_type") or "unknown"] += 1
        for blocker in row.get("blockers") or []:
            blockers[lang][blocker] += 1
    return {
        "rows": len(rows),
        "by_language": dict(by_lang),
        "top_repos_by_language": {
            lang: dict(counter.most_common(8)) for lang, counter in sorted(repo_counts.items())
        },
        "top_tasks_by_language": {
            lang: dict(counter.most_common(8)) for lang, counter in sorted(task_counts.items())
        },
        "blockers_by_language": {
            lang: dict(counter.most_common()) for lang, counter in sorted(blockers.items())
        },
    }


def make_request(seed: dict[str, Any]) -> dict[str, Any]:
    rows = seed["rows"]
    row_ids = sorted({row["row_id"] for row in rows})
    blockers = sorted({blocker for row in rows for blocker in (row.get("blockers") or [])})
    seed_source_files = sorted({row.get("source_file") for row in rows if row.get("source_file")})
    source_warnings = []
    if any(any(token in source for token in ("train", "support", "probe_request")) for source in seed_source_files):
        source_warnings.append(
            "seed_source_file_contains_train_or_support_marker; final admission must prove no train/support overlap"
        )
    return {
        "request_type": "source_heldout_smoke_root_materialization",
        "language_family": seed["language_family"],
        "repo_family": seed["repo_family"],
        "root_id": seed["root_id"],
        "seed_row_ids": row_ids,
        "seed_source_files": seed_source_files,
        "seed_source_warnings": source_warnings,
        "current_blockers": blockers,
        "required_repairs": [
            "attach explicit source_heldout_admissible=true or source_heldout attestation",
            "populate root_lineage_key and no-train/no-support split proof",
            "set deterministic_option_shuffle=true and persist shuffled opaque labels",
            "preserve opaque_labels=true and option_count>=2",
            "preserve prompt_target_value_leak=false and prompt_target_label_leak=false",
            "attach selected_test_anchor or verifier_anchor evidence",
            "attach has_verifier_row_or_transition=true evidence",
        ],
        "full_product_extension_required_repairs": [
            "attach patch_or_abstain signal",
            "emit harness_run_id",
            "emit same_task_pack_as_gemma12b=true",
            "emit tool_trace_spans",
            "emit verifier_results",
            "emit patch_minimality_or_abstain_scores",
        ],
        "acceptance": {
            "standalone_source_heldout_smoke_admissible": [
                "source_heldout_admissible=true",
                "root_lineage_key present",
                "train_eligible=false for smoke strict rows",
                "selected_test_anchor=true or verifier_anchor=true",
                "has_verifier_row_or_transition=true",
                "deterministic_option_shuffle=true",
                "opaque_labels=true",
                "option_count>=2",
                "prompt_target_value_leak=false",
            ],
            "full_product_harness_admissible": [
                "all standalone criteria pass",
                "has_patch_or_abstain_row=true",
                "harness writeback fields present",
                "same manifest can be scored by 100M and Gemma",
            ],
        },
    }


def main() -> None:
    if not NEAR_REPAIRABLE.exists():
        raise FileNotFoundError(NEAR_REPAIRABLE)
    if not STAGE11712.exists():
        raise FileNotFoundError(STAGE11712)

    rows = read_jsonl(NEAR_REPAIRABLE)
    stage11712 = read_json(STAGE11712)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    selected_by_language = {
        lang: select_seed_roots(rows, lang, max_roots=4) for lang in TARGET_LANGS
    }
    optional_selected = {
        lang: select_seed_roots(rows, lang, max_roots=2) for lang in OPTIONAL_LANGS
    }

    requests = [
        make_request(seed)
        for lang in TARGET_LANGS
        for seed in selected_by_language[lang]
    ]
    optional_requests = [
        make_request(seed)
        for lang in OPTIONAL_LANGS
        for seed in optional_selected[lang]
    ]

    target_root_counts = {lang: len(selected_by_language[lang]) for lang in TARGET_LANGS}
    request_ready = all(count > 0 for count in target_root_counts.values())

    artifact = {
        "stage": 11713,
        "stage_name": "source_heldout_smoke_materialization_request",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "source_heldout_smoke_materialization_requests_ready"
        if request_ready
        else "source_heldout_smoke_materialization_requests_incomplete",
        "passed": request_ready,
        "target": {
            "from_stage11712_work_item": "source_heldout_python_cpp_rust_smoke",
            "minimum": "one admitted source-heldout smoke root for python, c_cpp, and rust",
        },
        "pool_summary": summarize_pool(rows),
        "selected_root_counts": target_root_counts,
        "selected_roots_by_language": {
            lang: [
                {
                    "root_id": seed["root_id"],
                    "repo_family": seed["repo_family"],
                    "seed_rows": len(seed["rows"]),
                    "task_types": sorted({row.get("task_type") for row in seed["rows"]}),
                    "blockers": sorted(
                        {
                            blocker
                            for row in seed["rows"]
                            for blocker in (row.get("blockers") or [])
                        }
                    ),
                }
                for seed in selected_by_language[lang]
            ]
            for lang in TARGET_LANGS
        },
        "optional_web_roots": [
            {
                "root_id": seed["root_id"],
                "repo_family": seed["repo_family"],
                "seed_rows": len(seed["rows"]),
            }
            for seed in optional_selected.get("web_js_ts_html", [])
        ],
        "request_count": len(requests),
        "optional_request_count": len(optional_requests),
        "claim_boundary": [
            "This stage emits materialization/admission requests only; it does not admit rows.",
            "Seed rows remain non-promotable until source-heldout attestation, deterministic option shuffle, verifier/test anchors, and anti-cheat checks are repaired.",
            "Rows derived from prior compact/canary surfaces must not be used for broad source-heldout claims unless no-train/no-support lineage is proven.",
        ],
        "next_stage_acceptance": [
            "at least one admitted source-heldout smoke root for python, c_cpp, and rust",
            "no prompt target-value or target-label leaks",
            "deterministic option shuffle declared for every admitted row",
            "selected_test_anchor or verifier_anchor present",
            "root_lineage_key present and no train/support overlap",
        ],
        "stage11712_context": {
            "completion_status": stage11712["completion_status"],
            "source_heldout_status": stage11712["source_heldout_status"],
        },
        "source_artifacts": {
            "near_repairable": str(NEAR_REPAIRABLE.relative_to(ROOT)),
            "stage11712": str(STAGE11712.relative_to(ROOT)),
        },
        "outputs": {
            "artifact": "runs/local/artifacts/stage11713_source_heldout_smoke_materialization_request/source_heldout_smoke_materialization_request.json",
            "requests_jsonl": "runs/local/artifacts/stage11713_source_heldout_smoke_materialization_request/source_heldout_smoke_materialization_requests.jsonl",
            "optional_web_requests_jsonl": "runs/local/artifacts/stage11713_source_heldout_smoke_materialization_request/optional_web_source_heldout_requests.jsonl",
            "summary": "runs/summaries/stage11713_source_heldout_smoke_materialization_request.json",
        },
    }

    artifact_path = OUT_DIR / "source_heldout_smoke_materialization_request.json"
    requests_path = OUT_DIR / "source_heldout_smoke_materialization_requests.jsonl"
    optional_path = OUT_DIR / "optional_web_source_heldout_requests.jsonl"

    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with requests_path.open("w", encoding="utf-8") as fh:
        for req in requests:
            fh.write(json.dumps(req, sort_keys=True) + "\n")
    with optional_path.open("w", encoding="utf-8") as fh:
        for req in optional_requests:
            fh.write(json.dumps(req, sort_keys=True) + "\n")
    shutil.copyfile(artifact_path, SUMMARY_PATH)

    print(
        json.dumps(
            {
                "artifact": str(artifact_path),
                "summary": str(SUMMARY_PATH),
                "passed": artifact["passed"],
                "request_count": len(requests),
                "selected_root_counts": target_root_counts,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
