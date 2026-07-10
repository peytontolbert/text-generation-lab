#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10119
NAME = "stage10119_true_source_backed_maintainer_root_bundle_preview"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BUNDLES = OUT_DIR / "true_source_backed_maintainer_root_bundle_preview.jsonl"
MANIFEST = OUT_DIR / "true_source_backed_maintainer_root_bundle_preview_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_MAINTAINER_ROOT_BUNDLE_PREVIEW_STAGE10119.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

INVENTORY_PATH = ROOT / "runs/local/artifacts/session_like_source_inventory_real/packable_augmented_session_episode_examples_v4_dense_neighbors_realindex/packable_augmented_session_episode_examples.jsonl"
SCHEMA_10118 = ROOT / "runs/local/artifacts/stage10118_true_source_backed_maintainer_eval_bootstrap_schema/true_source_backed_maintainer_eval_bootstrap_schema.json"

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
LANGUAGE_QUOTAS = {"python": 3, "c_cpp": 3, "web_js_ts_html": 2}
MAX_SNIPPET_CHARS = 1200
MAX_CANDIDATE_PATHS = 6


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


def _context_rows(example: dict[str, Any]) -> list[dict[str, Any]]:
    rows = example.get("context_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _query(example: dict[str, Any]) -> dict[str, Any]:
    query = example.get("query")
    return query if isinstance(query, dict) else {}


def _repo_id(example: dict[str, Any]) -> str:
    metadata = example.get("metadata")
    if isinstance(metadata, dict):
        return str(metadata.get("repo_id") or "")
    return ""


def _source_route(example: dict[str, Any]) -> str:
    metadata = example.get("metadata")
    if isinstance(metadata, dict):
        source_metadata = metadata.get("source_metadata")
        if isinstance(source_metadata, dict):
            return str(source_metadata.get("route") or "")
    return ""


def _truncate(text: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _language_suffixes(paths: list[str]) -> set[str]:
    return {Path(path_text).suffix.lower() for path_text in paths if path_text}


def _paths_for_example(example: dict[str, Any]) -> list[str]:
    paths = [str(item).strip() for item in (_query(example).get("seed_paths") or []) if str(item).strip()]
    for row in _context_rows(example):
        if str(row.get("source_type") or "") != "local_repo":
            continue
        path_text = str(row.get("path") or "").strip()
        if path_text:
            paths.append(path_text)
    return list(dict.fromkeys(paths))


def _primary_language(example: dict[str, Any]) -> str:
    suffixes = _language_suffixes([str(item).strip() for item in (_query(example).get("seed_paths") or []) if str(item).strip()])
    if ".py" in suffixes:
        return "python"
    if any(suffix in {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss"} for suffix in suffixes):
        return "web_js_ts_html"
    if any(suffix in {".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx"} for suffix in suffixes):
        return "c_cpp"
    return ""


def _has_cpp_signal(example: dict[str, Any]) -> bool:
    suffixes = _language_suffixes(_paths_for_example(example))
    return any(suffix in {".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx"} for suffix in suffixes)


def _role_snippets(example: dict[str, Any], role: str, max_items: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in _context_rows(example):
        if str(row.get("role") or "") != role:
            continue
        items.append(
            {
                "path": str(row.get("path") or ""),
                "source_type": str(row.get("source_type") or ""),
                "retrieval_reason": str(row.get("retrieval_reason") or ""),
                "distance_from_seed": row.get("distance_from_seed"),
                "text": _truncate(str(row.get("text") or "")),
            }
        )
        if len(items) >= max_items:
            break
    return items


def _candidate_paths(example: dict[str, Any]) -> list[str]:
    paths = []
    for row in _context_rows(example):
        if str(row.get("source_type") or "") != "local_repo":
            continue
        role = str(row.get("role") or "")
        if role not in {"seed_change", "repo_graph_neighbor", "verification_constraint"}:
            continue
        path_text = str(row.get("path") or "").strip()
        if path_text:
            paths.append(path_text)
    return list(dict.fromkeys(paths))[:MAX_CANDIDATE_PATHS]


def _perspective_row(bundle_id: str, language_family: str, perspective: str, evidence: dict[str, list[dict[str, Any]]], candidate_paths: list[str], selected_tests: list[str]) -> dict[str, Any]:
    requirement_notes = {
        "symptom_localization": "Choose the most likely edit target from the visible failure and trace evidence.",
        "evidence_citation": "Name the visible fact that best supports the chosen edit target.",
        "alternative_hypothesis_elimination": "Explain why a plausible alternative target is less justified.",
        "patch_impact": "Compare candidate edits by likely behavior change and risk.",
        "verifier_outcome": "Predict which visible test or verification constraint should change if the fix is correct.",
        "minimal_fix_selection": "Choose the smallest maintainable intervention supported by the evidence.",
        "regression_risk": "Identify what the likely fix might break or destabilize.",
        "abstention_insufficient_evidence": "Decide whether the visible evidence is enough for a singleton answer or whether abstention is more honest.",
    }
    return {
        "bundle_id": bundle_id,
        "language_family": language_family,
        "perspective": perspective,
        "prompt_contract": {
            "task": requirement_notes[perspective],
            "candidate_paths": candidate_paths,
            "selected_tests": selected_tests,
            "visible_evidence_keys": sorted(key for key, value in evidence.items() if value),
            "abstention_option_required": perspective == "abstention_insufficient_evidence",
        },
        "gold_answer_status": "human_maintainer_adjudication_required",
        "eligible_for_training_or_scoring_now": False,
    }


def _bundle_from_example(example: dict[str, Any], *, language_family: str) -> dict[str, Any]:
    query = _query(example)
    selected_tests = [str(item) for item in (query.get("selected_tests") or []) if str(item).strip()]
    evidence = {
        "candidate_change_surface": _role_snippets(example, "seed_change", 3),
        "verifier_and_test_constraint": _role_snippets(example, "verification_constraint", 2),
        "symptom_or_call_path_analogue": _role_snippets(example, "trace_analogue", 2),
        "nearby_definition_or_usage_context": _role_snippets(example, "repo_graph_neighbor", 2),
        "external_analogue_reference": _role_snippets(example, "cross_repo_analogue", 1),
        "algorithmic_background_reference": _role_snippets(example, "algorithm_grounding", 1),
    }
    bundle_id = f"stage10119::{example.get('example_id')}::{language_family}"
    candidate_paths = _candidate_paths(example)
    return {
        "bundle_id": bundle_id,
        "root_example_id": example.get("example_id"),
        "repo_id": _repo_id(example),
        "language_family": language_family,
        "source_route": _source_route(example),
        "seed_paths": [str(item).strip() for item in (query.get("seed_paths") or []) if str(item).strip()],
        "selected_tests": selected_tests,
        "claim_boundary": {
            "gold_answers_fully_adjudicated": False,
            "supports_training_or_scoring_now": False,
            "preview_only": True,
        },
        "maintainer_visible_evidence": evidence,
        "candidate_paths": candidate_paths,
        "perspective_rows": [
            _perspective_row(bundle_id, language_family, perspective, evidence, candidate_paths, selected_tests)
            for perspective in PERSPECTIVES
        ],
    }


def build() -> dict[str, Any]:
    schema = load_json(SCHEMA_10118)
    examples = load_jsonl(INVENTORY_PATH)
    failures: list[str] = []
    if schema.get("passed") is not True:
        failures.append("stage10118_not_passed")

    selected: list[dict[str, Any]] = []
    counts = Counter()
    for example in examples:
        primary = _primary_language(example)
        if primary == "python" and counts["python"] < LANGUAGE_QUOTAS["python"]:
            selected.append(_bundle_from_example(example, language_family="python"))
            counts["python"] += 1
            continue
        if primary == "web_js_ts_html" and counts["web_js_ts_html"] < LANGUAGE_QUOTAS["web_js_ts_html"]:
            selected.append(_bundle_from_example(example, language_family="web_js_ts_html"))
            counts["web_js_ts_html"] += 1
            continue
        if _has_cpp_signal(example) and counts["c_cpp"] < LANGUAGE_QUOTAS["c_cpp"]:
            selected.append(_bundle_from_example(example, language_family="c_cpp"))
            counts["c_cpp"] += 1
            continue
        if sum(counts.values()) >= sum(LANGUAGE_QUOTAS.values()):
            break

    metrics = {
        "preview_root_bundles": len(selected),
        "bundle_language_counts": dict(sorted(counts.items())),
        "perspective_rows": sum(len(bundle["perspective_rows"]) for bundle in selected),
        "bundles_with_selected_tests": sum(1 for bundle in selected if bundle["selected_tests"]),
        "bundles_with_verifier_constraints": sum(1 for bundle in selected if bundle["maintainer_visible_evidence"]["verifier_and_test_constraint"]),
        "bundles_with_repo_graph_neighbors": sum(1 for bundle in selected if bundle["maintainer_visible_evidence"]["nearby_definition_or_usage_context"]),
    }
    if metrics["bundle_language_counts"] != {"c_cpp": 3, "python": 3, "web_js_ts_html": 2}:
        failures.append("preview_bundle_language_counts_unexpected")
    if metrics["preview_root_bundles"] != 8:
        failures.append("preview_root_bundles_not_8")
    if metrics["perspective_rows"] != 8 * len(PERSPECTIVES):
        failures.append("perspective_row_count_unexpected")

    manifest = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "source_inventory": display(INVENTORY_PATH),
            "bootstrap_schema": display(SCHEMA_10118),
            "bundles": display(BUNDLES),
        },
        "decision": (
            "Compiled the first tangible preview of a true source-backed maintainer eval: eight root bundles drawn from real session examples, "
            "each with bounded maintainer-visible evidence and eight perspective rows, while leaving gold answers blocked on human adjudication."
        ),
        "metrics": metrics,
        "claim_boundary": {
            "preview_only": True,
            "gold_answers_human_required": True,
            "supports_training_or_scoring_now": False,
            "rust_not_present": True,
        },
        "rows": [
            {
                "bundle_id": bundle["bundle_id"],
                "language_family": bundle["language_family"],
                "repo_id": bundle["repo_id"],
                "selected_tests": len(bundle["selected_tests"]),
                "candidate_paths": bundle["candidate_paths"],
            }
            for bundle in selected
        ],
        "next_best_step": (
            "Attach human gold adjudication and anti-cheat review to these root bundles, then expand the compiler beyond the preview packet while replenishing real Rust roots."
        ),
        "failures": failures,
    }
    return {"manifest": manifest, "bundles": selected}


def write_doc(manifest: dict[str, Any]) -> None:
    DOC.write_text(
        "\n".join(
            [
                "# Stage10119 True Source-Backed Maintainer Root Bundle Preview",
                "",
                f"Passed: `{manifest['passed']}`",
                f"Preview root bundles: `{manifest['metrics']['preview_root_bundles']}`",
                f"Perspective rows: `{manifest['metrics']['perspective_rows']}`",
                "",
                manifest["decision"],
                "",
                f"Next: {manifest['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    built = build()
    manifest = built["manifest"]
    write_jsonl(BUNDLES, built["bundles"])
    write_json(MANIFEST, manifest)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "name": NAME,
            "passed": manifest["passed"],
            "artifacts": manifest["artifacts"],
            "metrics": manifest["metrics"],
            "decision": manifest["decision"],
            "next_best_step": manifest["next_best_step"],
        },
    )
    write_doc(manifest)
    if manifest["passed"]:
        update_registry(
            {
                "passed": manifest["passed"],
                "next_best_step": manifest["next_best_step"],
            }
            | {"stage": STAGE, "stage_name": NAME}
        )
    print(json.dumps({"stage": STAGE, "passed": manifest["passed"], "metrics": manifest["metrics"], "failures": manifest["failures"]}, indent=2, sort_keys=True))
    if manifest["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
