#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

STAGE = 10538
NAME = "stage10538_compiled_root_expansion_inventory"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
AUDIT_JSON = OUT_DIR / "compiled_root_expansion_inventory.json"

COMPILED_ROWS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
CURRENT_MANIFEST = ROOT / "runs/local/artifacts/stage10530_leak_clean_root_based_multitarget_probe_request/leak_clean_root_based_multitarget_probe_manifest.jsonl"
EXPANSION_REQUEST = ROOT / "runs/local/artifacts/stage10537_multilingual_bootstrap_expansion_request/multilingual_bootstrap_expansion_request.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "roots": len({str(row.get("root_id") or "") for row in rows}),
        "repos": len({str(row.get("repo_id") or "") for row in rows}),
        "language_counts": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items())),
        "target_subtype_counts": dict(sorted(Counter(str(row.get("target_subtype") or "unknown") for row in rows).items())),
    }


def sample_roots(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    seen: set[str] = set()
    samples: list[dict[str, Any]] = []
    for row in rows:
        root_id = str(row.get("root_id") or "")
        if root_id in seen:
            continue
        seen.add(root_id)
        samples.append(
            {
                "root_id": root_id,
                "repo_id": str(row.get("repo_id") or ""),
                "language_family": str(row.get("language_family") or ""),
                "target_subtypes_present": [],
            }
        )
        if len(samples) >= limit:
            break
    return samples


def main() -> None:
    compiled_rows = load_jsonl(COMPILED_ROWS)
    compiled_roots = load_jsonl(COMPILED_ROOTS)
    manifest_rows = load_jsonl(CURRENT_MANIFEST)
    request = load_json(EXPANSION_REQUEST)

    used_root_ids = {str(row.get("root_id") or "") for row in manifest_rows}
    used_row_keys = {
        (
            str(row.get("root_id") or ""),
            str(row.get("target_subtype") or ""),
            str(row.get("row_id") or ""),
        )
        for row in manifest_rows
    }

    unused_rows = [row for row in compiled_rows if str(row.get("root_id") or "") not in used_root_ids]
    unused_roots = [row for row in compiled_roots if str(row.get("root_id") or "") not in used_root_ids]

    by_language_and_target: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in unused_rows:
        by_language_and_target[str(row.get("language_family") or "unknown")][str(row.get("target_subtype") or "unknown")].append(row)

    priority_inventory: list[dict[str, Any]] = []
    for item in request.get("expansion_priorities") or []:
        target_subtypes = list(((item.get("minimum_request") or {}).get("target_subtypes")) or [])
        languages = list(((item.get("minimum_request") or {}).get("languages")) or [])
        if not languages:
            # infer from request name when it targets a single lane
            name = str(item.get("name") or "")
            if name.startswith("rust_"):
                languages = ["rust"]
            elif name.startswith("web_"):
                languages = ["web_js_ts_html"]
            elif name.startswith("python_c_cpp_"):
                languages = ["python", "c_cpp"]
            else:
                languages = sorted(by_language_and_target.keys())
        lanes: dict[str, Any] = {}
        for language in languages:
            matches: list[dict[str, Any]] = []
            for subtype in target_subtypes:
                matches.extend(by_language_and_target.get(language, {}).get(subtype, []))
            root_ids = sorted({str(row.get("root_id") or "") for row in matches})
            repo_ids = sorted({str(row.get("repo_id") or "") for row in matches})
            subtype_counts = {
                subtype: len(by_language_and_target.get(language, {}).get(subtype, []))
                for subtype in target_subtypes
            }
            lane_samples = []
            root_to_subtypes: dict[str, set[str]] = defaultdict(set)
            for row in matches:
                root_to_subtypes[str(row.get("root_id") or "")].add(str(row.get("target_subtype") or "unknown"))
            for root_id in root_ids[:5]:
                exemplar = next(row for row in matches if str(row.get("root_id") or "") == root_id)
                lane_samples.append(
                    {
                        "root_id": root_id,
                        "repo_id": str(exemplar.get("repo_id") or ""),
                        "target_subtypes_present": sorted(root_to_subtypes[root_id]),
                    }
                )
            lanes[language] = {
                "candidate_rows": len(matches),
                "candidate_roots": len(root_ids),
                "candidate_repos": len(repo_ids),
                "target_subtype_counts": subtype_counts,
                "sample_roots": lane_samples,
            }
        priority_inventory.append(
            {
                "priority": item.get("priority"),
                "name": item.get("name"),
                "why": item.get("why"),
                "requested_target_subtypes": target_subtypes,
                "requested_languages": languages,
                "available_unused_inventory": lanes,
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Inventory of compiled but currently unused root/state rows that could satisfy the next multilingual bootstrap expansion request.",
            "Compares the existing stage10516 compiled supply against the current stage10530 manifest usage.",
            "This is a source-supply planning artifact, not a model-quality result.",
        ],
        "source_artifacts": {
            "compiled_rows": str(COMPILED_ROWS.relative_to(ROOT)),
            "compiled_roots": str(COMPILED_ROOTS.relative_to(ROOT)),
            "current_manifest": str(CURRENT_MANIFEST.relative_to(ROOT)),
            "expansion_request": str(EXPANSION_REQUEST.relative_to(ROOT)),
        },
        "current_manifest_usage": summarize_rows(manifest_rows),
        "compiled_supply": {
            "all_rows": summarize_rows(compiled_rows),
            "all_roots": len(compiled_roots),
            "unused_rows": summarize_rows(unused_rows),
            "unused_roots": len(unused_roots),
            "sample_unused_roots": sample_roots(unused_rows),
        },
        "priority_inventory": priority_inventory,
        "next_best_step": (
            "Use this inventory to decide whether stage10538 can be satisfied from existing compiled roots. "
            "If Rust/Web or heldout patch/action supply is absent here, mine fresh source roots rather than over-reusing the current compiler output."
        ),
    }

    write_json(AUDIT_JSON, payload)
    write_json(SUMMARY, payload)


if __name__ == "__main__":
    main()
