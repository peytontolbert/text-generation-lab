#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10124
NAME = "stage10124_true_source_backed_rust_replenishment_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "true_source_backed_rust_replenishment_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_RUST_REPLENISHMENT_REQUEST_STAGE10124.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BOOTSTRAP = ROOT / "runs/local/artifacts/stage10118_true_source_backed_maintainer_eval_bootstrap_schema/true_source_backed_maintainer_eval_bootstrap_schema.json"
PREVIEW = ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview_manifest.json"
ATLAS = ROOT / "runs/local/artifacts/stage10123_true_source_backed_root_bundle_review_priority_atlas/true_source_backed_root_bundle_review_priority_atlas.json"
MAIN_INVENTORY = ROOT / "runs/local/artifacts/session_like_source_inventory_real/packable_augmented_session_episode_examples_v4_dense_neighbors_realindex/packable_augmented_session_episode_examples.jsonl"
TRACEBACK_INVENTORY = ROOT / "runs/local/artifacts/session_like_source_inventory_real/session_episode_seed_candidates_traceback/session_episode_seed_candidates.jsonl"
SOURCE_REFS = ROOT / "runs/local/artifacts/stage8732_denoise_diffusion_repair_contract_graph_attachment/central_research_graph_with_denoise_diffusion_repair_contract_nodes.jsonl"

RUST_SUFFIXES = {".rs"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _row_paths(row: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for item in row.get("changes") or []:
        if isinstance(item, dict):
            text = str(item.get("path", "")).strip()
        else:
            text = str(item).strip()
        if text:
            paths.append(text)
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    for item in (query.get("seed_paths") or row.get("seed_paths") or []):
        text = str(item).strip()
        if text:
            paths.append(text)
    return paths


def _has_rust_path(paths: list[str]) -> bool:
    return any(Path(path_text).suffix.lower() in RUST_SUFFIXES for path_text in paths)


def _rust_inventory_metrics(path: Path) -> dict[str, int]:
    rows = load_jsonl(path)
    rust_rows = 0
    rust_path_refs = 0
    for row in rows:
        paths = _row_paths(row)
        rust_paths = [path_text for path_text in paths if Path(path_text).suffix.lower() in RUST_SUFFIXES]
        if rust_paths:
            rust_rows += 1
            rust_path_refs += len(rust_paths)
    return {
        "inventory_rows": len(rows),
        "rust_rows": rust_rows,
        "rust_path_references": rust_path_refs,
    }


def _external_graph_refs(path: Path) -> list[dict[str, str]]:
    rows = load_jsonl(path)
    wanted = {
        "/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl",
        "/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl",
    }
    best_by_path: dict[str, dict[str, str]] = {}
    for row in rows:
        row_path = str(row.get("path", "")).strip()
        if row_path not in wanted:
            continue
        candidate = {
            "path": row_path,
            "kind": str(row.get("kind", "")).strip(),
            "role": str(row.get("role", "") or "").strip(),
            "recovered_from": str(row.get("recovered_from", "")).strip(),
        }
        current = best_by_path.get(row_path)
        if current is None or (current.get("kind") != "source_ref" and candidate["kind"] == "source_ref"):
            best_by_path[row_path] = candidate
    refs = [best_by_path[path_text] for path_text in sorted(best_by_path)]
    return refs


def build() -> dict[str, Any]:
    bootstrap = load_json(BOOTSTRAP)
    preview = load_json(PREVIEW)
    atlas = load_json(ATLAS)
    main_inventory = _rust_inventory_metrics(MAIN_INVENTORY)
    traceback_inventory = _rust_inventory_metrics(TRACEBACK_INVENTORY)
    source_refs = _external_graph_refs(SOURCE_REFS)
    failures: list[str] = []

    if bootstrap.get("passed") is not True:
        failures.append("stage10118_not_passed")
    if preview.get("passed") is not True:
        failures.append("stage10119_not_passed")
    if atlas.get("passed") is not True:
        failures.append("stage10123_not_passed")
    if main_inventory["rust_rows"] != 0:
        failures.append("main_inventory_rust_rows_unexpected")
    if len(source_refs) != 2:
        failures.append("external_graph_refs_not_recovered")

    request = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "stage10118_bootstrap_schema": display(BOOTSTRAP),
            "stage10119_preview_manifest": display(PREVIEW),
            "stage10123_priority_atlas": display(ATLAS),
            "main_inventory": display(MAIN_INVENTORY),
            "traceback_inventory": display(TRACEBACK_INVENTORY),
            "recovered_external_graph_refs": display(SOURCE_REFS),
        },
        "intent": (
            "Replenish true source-backed rust maintainer roots from real external graph or session evidence so the v2.7 maintainer-grade evaluation can honestly cover python, rust, c_cpp, and web_js_ts_html."
        ),
        "claim_boundary": {
            "rust_present_in_current_source_backed_preview": False,
            "four_language_maintainer_claim_supported_now": False,
            "fresh_rust_source_backed_roots_required": True,
        },
        "current_evidence": {
            "bootstrap_primary_language_counts": ((bootstrap.get("metrics") or {}).get("primary_language_counts") or {}),
            "bootstrap_any_language_signal_counts": ((bootstrap.get("metrics") or {}).get("any_language_signal_counts") or {}),
            "preview_claim_boundary": preview.get("claim_boundary") or {},
            "main_inventory_rust_scan": main_inventory,
            "traceback_inventory_rust_scan": traceback_inventory,
            "atlas_rust_replenishment_required": bool(((atlas.get("metrics") or {}).get("rust_replenishment_required"))),
        },
        "upstream_source_routes": {
            "primary_external_graph_refs": source_refs,
            "current_session_inventory_recoverable_for_rust": main_inventory["rust_rows"] > 0 or traceback_inventory["rust_rows"] > 0,
        },
        "requirements": [
            "Source fresh rust roots from real external graph/session evidence rather than synthetic stage8636-stage8765 lineage.",
            "Materialize maintainer-visible failure text, trace or call-path evidence, candidate paths, and source snippets for every rust root.",
            "Preserve source-heldout lineage and anti-cheat provenance per root and split by root, repo, and source commit.",
            "Build the full 8-perspective maintainer bundle for each rust root, including abstention_insufficient_evidence.",
            "Store row-local graph/query handles or direct path/span evidence so later materialization does not collapse into templates again.",
            "Require opaque candidate IDs with candidate-order permutation support and shortcut review before any rust-vs-Gemma claim.",
        ],
        "target_replenishment": {
            "minimum_preview_ready_rust_bundles": 6,
            "minimum_first_wave_review_ready_rust_bundles": 2,
            "recommended_candidate_root_count": 12,
            "why": (
                "The current multilingual first wave covers two bundles each for web, python, and c_cpp. Rust needs at least two review-ready bundles to join that wave and a deeper reserve so same-manifest comparisons are not anchored on a tiny slice."
            ),
        },
        "sourcing_guidance": [
            "Start from /arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl and /arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl to recover real rust repos, paths, and spans.",
            "Prefer rust roots with at least two maintainer-plausible candidate surfaces and at least one executable or verifier-linked test/trace artifact.",
            "Bias toward roots that can expose implementation_vs_implementation, symbol_vs_symbol, and implementation_vs_config competition geometry.",
            "Reject roots that only expose a single obvious file or rely on path-name priors without concrete failure evidence.",
            "Keep rust roots source-heldout from training until same-manifest comparison and anti-cheat review are complete.",
        ],
        "failures": failures,
        "next_best_step": (
            "Implement a rust source discovery builder that pulls fresh roots from the recovered external graph refs, then convert the first accepted roots into true source-backed maintainer bundles before any four-language maintainer claim."
        ),
    }
    return request


def main() -> None:
    request = build()
    write_json(REQUEST, request)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": request["passed"],
        "metrics": {
            "main_inventory_rust_rows": request["current_evidence"]["main_inventory_rust_scan"]["rust_rows"],
            "traceback_inventory_rust_rows": request["current_evidence"]["traceback_inventory_rust_scan"]["rust_rows"],
            "minimum_preview_ready_rust_bundles": request["target_replenishment"]["minimum_preview_ready_rust_bundles"],
            "minimum_first_wave_review_ready_rust_bundles": request["target_replenishment"]["minimum_first_wave_review_ready_rust_bundles"],
            "recommended_candidate_root_count": request["target_replenishment"]["recommended_candidate_root_count"],
            "failures": request["failures"],
        },
        "artifacts": request["artifacts"],
        "decision": (
            "Confirmed that the current true source-backed maintainer path has zero recoverable rust coverage in the live inventory and converted that gap into an explicit replenishment request tied to the recovered external graph sources."
        ),
        "next_best_step": request["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10124 True Source-Backed Rust Replenishment Request",
                "",
                f"Passed: `{summary['passed']}`",
                f"Main inventory rust rows: `{summary['metrics']['main_inventory_rust_rows']}`",
                f"Traceback inventory rust rows: `{summary['metrics']['traceback_inventory_rust_rows']}`",
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
    print(json.dumps({"stage": STAGE, "passed": request["passed"], "failures": request["failures"]}, indent=2, sort_keys=True))
    if request["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
