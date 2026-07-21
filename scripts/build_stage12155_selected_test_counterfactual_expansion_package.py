#!/usr/bin/env python3
"""Build Stage12155 selected-test counterfactual expansion package."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_stage12153_counterfactual_selected_test_transition_rows import (
    TASKS,
    VARIANTS,
    build_row as build_counterfactual_row,
    safety_audit,
    utility_audit,
)


STAGE = "stage12155_selected_test_counterfactual_expansion_package"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_MIRROR = ROOT / "runs/summaries" / f"{STAGE}.json"

BASE_ROWS = ROOT / "runs/local/artifacts/stage12153_counterfactual_selected_test_transition_rows/counterfactual_selected_test_rows.jsonl"
STAGE12154_SUMMARY = ROOT / "runs/summaries/stage12154_counterfactual_selected_test_training_utility_audit.json"
STAGE12148_CONTRACT = ROOT / "runs/local/artifacts/stage12148_task_specific_selected_test_materialization_contract/materialization_contract.json"
STAGE12150_SCRIPT = ROOT / "scripts/build_stage12150_corrected_selected_test_materialization_audit.py"
STAGE12152_SCRIPT = ROOT / "scripts/build_stage12152_selected_test_training_utility_audit.py"

DEPENDENCY_PARTS = {
    ".git",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "venv",
}


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def blocked_path(rel: str) -> bool:
    return bool(set(Path(rel).parts) & DEPENDENCY_PARTS)


def file_hashes(root: Path, source_paths: list[str], test_paths: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    blockers: list[str] = []
    records: list[dict[str, str]] = []
    for kind, paths in (("source", source_paths), ("test", test_paths)):
        for rel in paths:
            if blocked_path(rel):
                blockers.append(f"dependency_or_build_path::{rel}")
                continue
            path = root / rel
            if not path.is_file():
                blockers.append(f"missing_{kind}_path::{rel}")
                continue
            records.append({"kind": kind, "path": rel, "sha256": sha256_file(path)})
    if not any(r["kind"] == "source" for r in records):
        blockers.append("missing_source_hash")
    if not any(r["kind"] == "test" for r in records):
        blockers.append("missing_test_hash")
    return records, blockers


def root_specs() -> list[dict[str, Any]]:
    tmp = Path("/data/tmp")
    return [
        {
            "repo_family": "pallets/click",
            "root_id": "stage12118::python::016::pallets_click",
            "language_family": "python",
            "checkout": tmp / "stage12123_verifier_ready_smoke_repos/pallets_click",
            "commit_sha": "b67832c2167e5b0ff6764a8c04a0a9087e697b5a",
            "selected_test_count": 102,
            "source_stage": "stage12123",
            "source_paths": ["src/click/core.py", "src/click/decorators.py", "src/click/types.py", "src/click/utils.py"],
            "test_paths": ["tests/test_basic.py", "tests/conftest.py"],
            "verifier_evidence_type": "pytest_selected_file_passed",
            "sanitized_verifier_command": "PYTHONPATH=src python -m pytest -q tests/test_basic.py",
        },
        {
            "repo_family": "pallets/jinja",
            "root_id": "stage12118::python::018::pallets_jinja",
            "language_family": "python",
            "checkout": tmp / "stage12123_verifier_ready_smoke_repos/pallets_jinja",
            "commit_sha": "5ef70112a1ff19c05324ff889dd30405b1002044",
            "selected_test_count": 34,
            "source_stage": "stage12123",
            "source_paths": ["src/jinja2/environment.py", "src/jinja2/runtime.py", "src/jinja2/meta.py", "src/jinja2/nodes.py"],
            "test_paths": ["tests/test_api.py", "tests/conftest.py"],
            "verifier_evidence_type": "pytest_selected_file_passed",
            "sanitized_verifier_command": "PYTHONPATH=src python -m pytest -q tests/test_api.py",
        },
        {
            "repo_family": "moment/luxon",
            "root_id": "stage12118::web_js_ts_html::024::moment_luxon",
            "language_family": "web_js_ts_html",
            "checkout": tmp / "stage12128b_rust_web_smoke_repos/stage12118__web_js_ts_html__024__moment_luxon",
            "commit_sha": "b6b9d03709085008287ed7f4ce5067f0f4be53f2",
            "selected_test_count": 93,
            "source_stage": "stage12155_repaired_luxon_clean_paths",
            "source_paths": ["src/datetime.js", "src/settings.js", "src/info.js", "src/errors.js"],
            "test_paths": ["test/datetime/create.test.js", "test/helpers.js", "test/setupTests.js"],
            "verifier_evidence_type": "jest_selected_file_passed_repaired_clean_source_paths",
            "sanitized_verifier_command": "TZ=America/New_York npm run jest -- --runInBand test/datetime/create.test.js",
        },
        {
            "repo_family": "Neargye/magic_enum",
            "root_id": "stage12118::c_cpp::002::Neargye_magic_enum",
            "language_family": "c_cpp",
            "checkout": tmp / "stage12123_verifier_ready_smoke_repos/Neargye_magic_enum",
            "commit_sha": "6336b3a8295f9c9ff0522ed37f4f444f2e56c881",
            "selected_test_count": 1,
            "source_stage": "stage12125",
            "source_paths": [
                "include/magic_enum/magic_enum.hpp",
                "include/magic_enum/magic_enum_all.hpp",
                "include/magic_enum/magic_enum_containers.hpp",
                "include/magic_enum/magic_enum_flags.hpp",
            ],
            "test_paths": ["test/test.cpp", "test/test_helpers.hpp", "test/CMakeLists.txt"],
            "verifier_evidence_type": "exact_ctest_regex_passed",
            "sanitized_verifier_command": "ctest --test-dir <withheld-build-dir> --output-on-failure -R ^test-cpp17$",
        },
        {
            "repo_family": "fastfloat/fast_float",
            "root_id": "stage12118::c_cpp::019::fastfloat_fast_float",
            "language_family": "c_cpp",
            "checkout": tmp / "stage12123_verifier_ready_smoke_repos/fastfloat_fast_float",
            "commit_sha": "f6df0f29174054bb1ed06a9945416c8946a01292",
            "selected_test_count": 1,
            "source_stage": "stage12125",
            "source_paths": [
                "include/fast_float/fast_float.h",
                "include/fast_float/parse_number.h",
                "include/fast_float/float_common.h",
                "include/fast_float/decimal_to_binary.h",
            ],
            "test_paths": ["tests/basictest.cpp", "tests/CMakeLists.txt"],
            "verifier_evidence_type": "exact_ctest_regex_passed",
            "sanitized_verifier_command": "ctest --test-dir <withheld-build-dir> --output-on-failure -R ^basictest$",
        },
    ]


def materializable_roots() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for spec in root_specs():
        blockers: list[str] = []
        checkout = spec["checkout"]
        if not checkout.is_dir():
            blockers.append("missing_checkout")
        if not spec.get("commit_sha"):
            blockers.append("missing_commit_sha")
        hashes, hash_blockers = file_hashes(checkout, spec["source_paths"], spec["test_paths"]) if checkout.is_dir() else ([], ["missing_hashes"])
        blockers.extend(hash_blockers)
        if spec["repo_family"] == "moment/luxon" and spec["commit_sha"] != "b6b9d03709085008287ed7f4ce5067f0f4be53f2":
            blockers.append("luxon_commit_sha_mismatch")
        if spec["repo_family"] == "moment/luxon" and any("node_modules" in h["path"] for h in hashes):
            blockers.append("luxon_node_modules_path_in_hashes")
        if blockers:
            excluded.append({"repo_family": spec["repo_family"], "root_id": spec["root_id"], "blockers": sorted(set(blockers))})
            continue
        included.append(
            {
                "root_id": spec["root_id"],
                "repo_family": spec["repo_family"],
                "language_family": spec["language_family"],
                "commit_sha": spec["commit_sha"],
                "selected_test_count": spec["selected_test_count"],
                "source_test_hashes": hashes,
                "source_stage": spec["source_stage"],
                "verifier_evidence_type": spec["verifier_evidence_type"],
                "sanitized_verifier_command": spec["sanitized_verifier_command"],
            }
        )
    return included, excluded


def rewrite_stage(row: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(row))
    out["stage"] = STAGE
    out["surface"] = "stage12155_selected_test_counterfactual_expansion_train_support"
    out["split_role"] = "stage12155_counterfactual_expansion_train_support_only_not_strict_eval"
    out["row_id"] = out["row_id"].replace("stage12153::", "stage12155::", 1)
    out["strict_eval_eligible"] = False
    out["training_allowed"] = False
    out["promotion_eligible"] = False
    out["train_support_only"] = True
    out["counterfactual_train_support_only"] = True
    projection = out.get("standalone_projection_source") or {}
    projection["stage"] = STAGE
    projection["source_package"] = "stage12155_expansion_regenerated_from_clean_provenance"
    projection["counterfactual_train_support_only"] = True
    projection["verifier_evidence_type"] = root["verifier_evidence_type"]
    projection["sanitized_verifier_command"] = root["sanitized_verifier_command"]
    projection["provenance_adequate_for_train_support"] = True
    out["standalone_projection_source"] = projection
    anti = out.get("anti_cheat") or {}
    anti["stage12155_train_support_only"] = True
    out["anti_cheat"] = anti
    return out


def row_count_tables(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_task_target = defaultdict(Counter)
    by_variant_task_target = defaultdict(Counter)
    for row in rows:
        target = str((row.get("target") or {}).get("semantic_value") or row.get("target_semantic_value") or "")
        by_task_target[row["task_type"]][target] += 1
        by_variant_task_target[f"{row.get('state_variant')}::{row['task_type']}"][target] += 1
    return {
        "row_counts_by_task_target": {key: dict(sorted(counter.items())) for key, counter in sorted(by_task_target.items())},
        "row_counts_by_state_variant_task_target": {key: dict(sorted(counter.items())) for key, counter in sorted(by_variant_task_target.items())},
    }


def main() -> None:
    base_rows = read_jsonl(BASE_ROWS)
    stage12154 = read_json(STAGE12154_SUMMARY)
    contract = read_json(STAGE12148_CONTRACT)
    included_roots, excluded_roots = materializable_roots()
    expansion_rows: list[dict[str, Any]] = []
    for root in included_roots:
        for variant in VARIANTS:
            for task in TASKS:
                expansion_rows.append(rewrite_stage(build_counterfactual_row(root, variant, task), root))
    rows = base_rows + expansion_rows
    safety = safety_audit(rows)
    utility = utility_audit(rows)
    counts = row_count_tables(rows)
    languages = sorted({row["language_family"] for row in rows})
    root_ids = sorted({row["root_id"] for row in rows})
    repo_families = sorted({row["repo_family"] for row in rows})
    audit = {
        "stage": STAGE,
        "created_at_utc": now(),
        "inputs": {
            "stage12153_rows": str(BASE_ROWS.relative_to(ROOT)),
            "stage12154_summary": str(STAGE12154_SUMMARY.relative_to(ROOT)),
            "stage12148_contract": str(STAGE12148_CONTRACT.relative_to(ROOT)),
            "stage12150_script": str(STAGE12150_SCRIPT.relative_to(ROOT)),
            "stage12152_script": str(STAGE12152_SCRIPT.relative_to(ROOT)),
        },
        "contract_task_families": sorted((contract.get("row_families") or {}).keys()),
        "source_stage12154_blockers": stage12154.get("blockers", []),
        "base_row_count": len(base_rows),
        "expansion_row_count": len(expansion_rows),
        "row_count": len(rows),
        "root_count": len(root_ids),
        "language_count": len(languages),
        "languages": languages,
        "roots_included": repo_families,
        "expansion_roots_included": included_roots,
        "expansion_roots_excluded": excluded_roots,
        "safety_validation": safety,
        "stage12152_style_utility_audit": utility,
        "stage12152_cli_note": "Stage12152 CLI is hardcoded to Stage12149 input; equivalent Stage12152 utility logic was run against expanded_counterfactual_rows.jsonl here.",
        **counts,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "promotion_eligible": False,
    }
    summary = {
        "stage": STAGE,
        "created_at_utc": audit["created_at_utc"],
        "rows": len(rows),
        "base_rows": len(base_rows),
        "expansion_rows": len(expansion_rows),
        "root_count": len(root_ids),
        "language_count": len(languages),
        "languages": languages,
        "roots_included": repo_families,
        "expansion_roots_excluded": excluded_roots,
        "safety_passed": safety["passed"],
        "stage12152_style_passed": utility["stage12152_style_passed"],
        "stage12152_style_blockers": utility["blockers"],
        "future_training_request_blocked": bool(utility["blockers"]) or not safety["passed"],
        "strict_eval_eligible": False,
        "training_allowed": False,
        "promotion_eligible": False,
        "train_support_only": True,
        "outputs": {
            "rows": str((OUT / "expanded_counterfactual_rows.jsonl").relative_to(ROOT)),
            "audit": str((OUT / "expansion_audit.json").relative_to(ROOT)),
            "summary": str((OUT / "summary.json").relative_to(ROOT)),
            "summary_mirror": str(SUMMARY_MIRROR.relative_to(ROOT)),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "expanded_counterfactual_rows.jsonl", rows)
    write_json(OUT / "expansion_audit.json", audit)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY_MIRROR, summary)


if __name__ == "__main__":
    main()
