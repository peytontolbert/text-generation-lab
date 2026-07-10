#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10125
NAME = "stage10125_true_source_backed_rust_root_discovery_manifest"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "true_source_backed_rust_root_discovery_manifest.json"
CANDIDATES = OUT_DIR / "true_source_backed_rust_root_candidates.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_RUST_ROOT_DISCOVERY_MANIFEST_STAGE10125.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUEST = ROOT / "runs/local/artifacts/stage10124_true_source_backed_rust_replenishment_request/true_source_backed_rust_replenishment_request.json"
SPANS = Path("/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl")

COMMON_PREFIXES = {"src", "tests", "test", "examples", "benches"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _split_span_path(span_id: str) -> tuple[str, str]:
    if ":" in span_id:
        repo, path_text = span_id.split(":", 1)
        return repo, path_text
    return "unknown", span_id


def _package_root(path_text: str) -> str:
    parts = [part for part in Path(path_text).parts if part]
    if not parts:
        return path_text
    if len(parts) == 1:
        return parts[0]
    first = parts[0]
    second = parts[1]
    if first in {"bindings", "contrib", "samples"} and len(parts) >= 2:
        return "/".join(parts[:2])
    if second in COMMON_PREFIXES:
        return first
    return first


def _classify_path(path_text: str) -> str:
    lower = path_text.lower()
    name = Path(lower).name
    if "/tests/" in lower or lower.startswith("tests/") or name.endswith("_tests.rs") or name.startswith("test_"):
        return "test"
    if name == "build.rs":
        return "build"
    if name in {"lib.rs", "main.rs"} or "/src/" in lower or lower.startswith("src/"):
        return "implementation"
    return "support"


def _competition_geometries(kinds: Counter[str]) -> list[str]:
    tags: list[str] = []
    if kinds["implementation"] >= 2:
        tags.append("implementation_vs_implementation")
        tags.append("symbol_vs_symbol")
    if kinds["implementation"] >= 1 and kinds["test"] >= 1:
        tags.append("implementation_vs_test")
    if kinds["implementation"] >= 1 and kinds["build"] >= 1:
        tags.append("implementation_vs_build")
    return sorted(set(tags))


def build() -> dict[str, Any]:
    request = load_json(REQUEST)
    failures: list[str] = []
    if request.get("passed") is not True:
        failures.append("stage10124_not_passed")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    repo_counts = Counter()
    rust_row_count = 0
    with SPANS.open("r", encoding="utf-8") as handle:
        for line in handle:
            obj = json.loads(line)
            span_id = str(obj.get("span_id", "")).strip()
            if not span_id.endswith(".rs") and ".rs" not in span_id:
                continue
            meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
            if str(meta.get("kind", "")).strip() != "code":
                continue
            repo_id = str(meta.get("corpus") or _split_span_path(span_id)[0]).strip() or "unknown"
            _, path_text = _split_span_path(span_id)
            if Path(path_text).suffix.lower() != ".rs":
                continue
            rust_row_count += 1
            repo_counts[repo_id] += 1
            package_root = _package_root(path_text)
            key = (repo_id, package_root)
            group = grouped.setdefault(
                key,
                {
                    "repo_id": repo_id,
                    "package_root": package_root,
                    "paths": set(),
                    "path_kinds": Counter(),
                    "sample_span_ids": [],
                },
            )
            group["paths"].add(path_text)
            kind = _classify_path(path_text)
            group["path_kinds"][kind] += 1
            if len(group["sample_span_ids"]) < 3:
                group["sample_span_ids"].append(span_id)

    candidates: list[dict[str, Any]] = []
    for group in grouped.values():
        path_kinds: Counter[str] = group["path_kinds"]
        rust_paths = sorted(group["paths"])
        implementation_paths = [p for p in rust_paths if _classify_path(p) == "implementation"]
        test_paths = [p for p in rust_paths if _classify_path(p) == "test"]
        build_paths = [p for p in rust_paths if _classify_path(p) == "build"]
        support_paths = [p for p in rust_paths if _classify_path(p) == "support"]
        geometries = _competition_geometries(path_kinds)
        richness = min(len(implementation_paths), 4) * 3 + min(len(test_paths), 3) * 2 + min(len(build_paths), 2) + min(len(support_paths), 2)
        if test_paths:
            richness += 2
        if build_paths:
            richness += 1
        if len(rust_paths) >= 4:
            richness += 1
        review_ready = bool(implementation_paths and (test_paths or build_paths) and len(rust_paths) >= 2)
        candidates.append(
            {
                "repo_id": group["repo_id"],
                "package_root": group["package_root"],
                "candidate_root_id": f"{group['repo_id']}::{group['package_root']}",
                "rust_file_count": len(rust_paths),
                "implementation_file_count": len(implementation_paths),
                "test_file_count": len(test_paths),
                "build_file_count": len(build_paths),
                "support_file_count": len(support_paths),
                "competition_geometries": geometries,
                "review_ready_for_bundle_construction": review_ready,
                "richness_score": richness,
                "candidate_paths_preview": rust_paths[:12],
                "sample_span_ids": group["sample_span_ids"],
            }
        )

    candidates.sort(
        key=lambda row: (
            not row["review_ready_for_bundle_construction"],
            -row["richness_score"],
            -row["rust_file_count"],
            row["repo_id"],
            row["package_root"],
        )
    )
    for idx, row in enumerate(candidates, start=1):
        row["queue_position"] = idx

    metrics = {
        "rust_span_rows": rust_row_count,
        "rust_repo_count": len(repo_counts),
        "repo_span_counts": dict(sorted(repo_counts.items())),
        "candidate_root_count": len(candidates),
        "review_ready_candidates": sum(1 for row in candidates if row["review_ready_for_bundle_construction"]),
        "top_review_ready_candidates": [
            row["candidate_root_id"] for row in candidates if row["review_ready_for_bundle_construction"]
        ][:12],
    }
    if metrics["rust_repo_count"] < 3:
        failures.append("rust_repo_count_too_small")
    if metrics["review_ready_candidates"] < 2:
        failures.append("review_ready_candidates_below_minimum")

    manifest = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "artifacts": {
            "rust_replenishment_request": display(REQUEST),
            "spans_graph": str(SPANS),
            "candidate_rows": display(CANDIDATES),
        },
        "metrics": metrics,
        "rows": candidates,
        "failures": failures,
        "next_best_step": (
            "Convert the top review-ready rust candidates into true source-backed maintainer root bundles with maintainer-visible evidence, then route them into the Stage10122/10123 adjudication path."
        ),
    }
    return manifest


def main() -> None:
    built = build()
    write_json(MANIFEST, built)
    write_jsonl(CANDIDATES, built["rows"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {
            "rust_repo_count": built["metrics"]["rust_repo_count"],
            "candidate_root_count": built["metrics"]["candidate_root_count"],
            "review_ready_candidates": built["metrics"]["review_ready_candidates"],
            "failures": built["failures"],
        },
        "artifacts": built["artifacts"],
        "decision": (
            "Discovered real rust candidate roots directly from the recovered spans graph and ranked them for maintainer-grade bundle construction instead of leaving rust coverage as a pure request."
        ),
        "next_best_step": built["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10125 True Source-Backed Rust Root Discovery Manifest",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rust repo count: `{summary['metrics']['rust_repo_count']}`",
                f"Candidate root count: `{summary['metrics']['candidate_root_count']}`",
                f"Review-ready candidates: `{summary['metrics']['review_ready_candidates']}`",
                "",
                summary["decision"],
                "",
                f"Next: {summary['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "failures": built["failures"], "metrics": built["metrics"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
