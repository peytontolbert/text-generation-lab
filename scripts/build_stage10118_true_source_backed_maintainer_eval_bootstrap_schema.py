#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10118
NAME = "stage10118_true_source_backed_maintainer_eval_bootstrap_schema"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SCHEMA = OUT_DIR / "true_source_backed_maintainer_eval_bootstrap_schema.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_MAINTAINER_EVAL_BOOTSTRAP_SCHEMA_STAGE10118.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

INVENTORY_PATH = ROOT / "runs/local/artifacts/session_like_source_inventory_real/packable_augmented_session_episode_examples_v4_dense_neighbors_realindex/packable_augmented_session_episode_examples.jsonl"
CONTRACT_10117 = ROOT / "runs/local/artifacts/stage10117_true_source_backed_maintainer_eval_replacement_contract/true_source_backed_maintainer_eval_replacement_contract.json"

ROLE_TO_EVIDENCE = {
    "seed_change": "candidate_change_surface",
    "verification_constraint": "verifier_and_test_constraint",
    "trace_analogue": "symptom_or_call_path_analogue",
    "repo_graph_neighbor": "nearby_definition_or_usage_context",
    "cross_repo_analogue": "external_analogue_reference",
    "algorithm_grounding": "algorithmic_background_reference",
}

PERSPECTIVE_REQUIREMENTS = {
    "symptom_localization": ["candidate_change_surface", "symptom_or_call_path_analogue"],
    "evidence_citation": ["candidate_change_surface", "symptom_or_call_path_analogue", "nearby_definition_or_usage_context"],
    "alternative_hypothesis_elimination": ["candidate_change_surface", "nearby_definition_or_usage_context"],
    "patch_impact": ["candidate_change_surface", "verifier_and_test_constraint"],
    "verifier_outcome": ["verifier_and_test_constraint", "symptom_or_call_path_analogue"],
    "minimal_fix_selection": ["candidate_change_surface", "nearby_definition_or_usage_context"],
    "regression_risk": ["candidate_change_surface", "verifier_and_test_constraint", "external_analogue_reference"],
    "abstention_insufficient_evidence": ["candidate_change_surface"],
}


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


def _context_rows(example: dict[str, Any]) -> list[dict[str, Any]]:
    rows = example.get("context_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _repo_id(example: dict[str, Any]) -> str:
    metadata = example.get("metadata")
    if isinstance(metadata, dict):
        return str(metadata.get("repo_id") or "")
    return ""


def _changed_paths(example: dict[str, Any]) -> list[str]:
    query = example.get("query")
    if isinstance(query, dict):
        seed_paths = query.get("seed_paths")
        if isinstance(seed_paths, list):
            return [str(item) for item in seed_paths if str(item).strip()]
    return []


def _language_family_from_paths(paths: list[str]) -> str:
    suffixes = {Path(path).suffix.lower() for path in paths}
    if any(suffix == ".py" for suffix in suffixes):
        return "python"
    if any(suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"} for suffix in suffixes):
        return "c_cpp"
    if any(suffix in {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss"} for suffix in suffixes):
        return "web_js_ts_html"
    if any(suffix == ".rs" for suffix in suffixes):
        return "rust"
    return ""


def _language_family_from_example(example: dict[str, Any]) -> str:
    changed_paths = _changed_paths(example)
    language = _language_family_from_paths(changed_paths)
    if language:
        return language
    local_repo_paths = []
    for row in _context_rows(example):
        if str(row.get("source_type") or "") != "local_repo":
            continue
        path_text = str(row.get("path") or "").strip()
        if path_text:
            local_repo_paths.append(path_text)
    return _language_family_from_paths(local_repo_paths)


def build() -> dict[str, Any]:
    contract_10117 = load_json(CONTRACT_10117)
    examples = load_jsonl(INVENTORY_PATH)
    failures: list[str] = []
    if contract_10117.get("passed") is not True:
        failures.append("stage10117_not_passed")
    if len(examples) != 56:
        failures.append("expected_56_examples_in_bootstrap_inventory")

    role_counts = Counter()
    primary_language_counts = Counter()
    any_language_signal_counts = Counter()
    repo_counts = Counter()
    perspective_support_counts = Counter()
    selected_test_rows = 0
    bootstrap_examples: list[dict[str, Any]] = []

    for example in examples:
        context_rows = _context_rows(example)
        changed_paths = _changed_paths(example)
        language = _language_family_from_example(example)
        if language:
            primary_language_counts[language] += 1
        all_paths = list(changed_paths)
        for row in context_rows:
            if str(row.get("source_type") or "") != "local_repo":
                continue
            path_text = str(row.get("path") or "").strip()
            if path_text:
                all_paths.append(path_text)
        suffixes = {Path(path_text).suffix.lower() for path_text in all_paths if path_text}
        if any(suffix == ".py" for suffix in suffixes):
            any_language_signal_counts["python"] += 1
        if any(suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".cu"} for suffix in suffixes):
            any_language_signal_counts["c_cpp"] += 1
        if any(suffix in {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss"} for suffix in suffixes):
            any_language_signal_counts["web_js_ts_html"] += 1
        if any(suffix == ".rs" for suffix in suffixes):
            any_language_signal_counts["rust"] += 1
        repo_id = _repo_id(example)
        if repo_id:
            repo_counts[repo_id] += 1
        query = example.get("query")
        selected_tests = query.get("selected_tests") if isinstance(query, dict) else []
        if isinstance(selected_tests, list) and selected_tests:
            selected_test_rows += 1

        role_evidence = {ROLE_TO_EVIDENCE.get(str(row.get("role") or "")) for row in context_rows}
        role_evidence.discard(None)
        for row in context_rows:
            role_counts[str(row.get("role") or "")] += 1
        for perspective, needed in PERSPECTIVE_REQUIREMENTS.items():
            if set(needed).issubset(role_evidence):
                perspective_support_counts[perspective] += 1

        if len(bootstrap_examples) < 6:
            bootstrap_examples.append(
                {
                    "example_id": example.get("example_id"),
                    "repo_id": repo_id,
                    "language_family": language,
                    "seed_paths": changed_paths,
                    "selected_tests": selected_tests,
                    "available_roles": sorted(str(row.get("role") or "") for row in context_rows if str(row.get("role") or "")),
                    "available_evidence_types": sorted(role_evidence),
                    "source_route": ((example.get("metadata") or {}).get("source_metadata") or {}).get("route"),
                    "target_label_surface": (example.get("targets") or {}).get("final_answer"),
                }
            )

    metrics = {
        "bootstrap_inventory_examples": len(examples),
        "primary_language_counts": dict(sorted(primary_language_counts.items())),
        "any_language_signal_counts": dict(sorted(any_language_signal_counts.items())),
        "repo_counts": dict(sorted(repo_counts.items())),
        "selected_test_rows": selected_test_rows,
        "context_role_counts": dict(sorted(role_counts.items())),
        "perspective_support_counts": dict(sorted(perspective_support_counts.items())),
        "perspectives_fully_bootstrappable_now": sorted(
            perspective for perspective, count in perspective_support_counts.items() if count > 0
        ),
    }
    if metrics["primary_language_counts"] != {"python": 49, "web_js_ts_html": 5}:
        failures.append("unexpected_primary_language_counts")
    if metrics["any_language_signal_counts"] != {"c_cpp": 9, "python": 49, "web_js_ts_html": 6}:
        failures.append("unexpected_any_language_signal_counts")
    if perspective_support_counts["abstention_insufficient_evidence"] != len(examples):
        failures.append("abstention_perspective_should_be_possible_for_all_examples")

    schema = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "source_inventory": display(INVENTORY_PATH),
            "replacement_contract": display(CONTRACT_10117),
        },
        "decision": (
            "Mapped the live true source-backed session reservoir into an executable maintainer-eval bootstrap schema: "
            "a source example is not itself the eval row, but it already contains enough role-typed evidence to compile root bundles for Python, C/C++, and Web."
        ),
        "root_bundle_schema": {
            "root_id_fields": ["example_id", "repo_id", "seed_paths"],
            "root_metadata_fields": ["language_family", "source_route", "selected_tests", "difficulty", "quality"],
            "evidence_materialization_fields": {
                "candidate_change_surface": ["context_rows where role == seed_change"],
                "verifier_and_test_constraint": ["context_rows where role == verification_constraint", "query.selected_tests"],
                "symptom_or_call_path_analogue": ["context_rows where role == trace_analogue"],
                "nearby_definition_or_usage_context": ["context_rows where role == repo_graph_neighbor"],
                "external_analogue_reference": ["context_rows where role == cross_repo_analogue"],
                "algorithmic_background_reference": ["context_rows where role == algorithm_grounding"],
            },
            "perspective_requirements": PERSPECTIVE_REQUIREMENTS,
            "row_compiler_rules": [
                "truncate raw context rows into maintainer-visible snippet spans rather than full 200k-character blobs",
                "derive candidate paths from seed_change and repo_graph_neighbor local_repo rows",
                "emit abstention when verifier, trace, or local code evidence is insufficient for a singleton decision",
                "keep external analogue and algorithm grounding rows as optional support, never sole grounds for the gold answer",
                "split by root example_id and repo_id, never by derived perspective row",
            ],
        },
        "bootstrap_examples": bootstrap_examples,
        "claim_boundary": {
            "python_bootstrap_ready": metrics["primary_language_counts"].get("python", 0) > 0,
            "c_cpp_bootstrap_ready": metrics["any_language_signal_counts"].get("c_cpp", 0) > 0,
            "web_bootstrap_ready": metrics["primary_language_counts"].get("web_js_ts_html", 0) > 0,
            "rust_bootstrap_ready": False,
            "inventory_rows_are_raw_source_examples_not_final_eval_rows": True,
        },
        "metrics": metrics,
        "next_best_step": (
            "Implement the root-bundle compiler over this inventory: materialize maintainer-visible snippet spans from seed_change, verification_constraint, "
            "trace_analogue, and repo_graph_neighbor rows, then emit multi-perspective bundles for python, c_cpp, and web while Rust replenishment proceeds separately."
        ),
        "failures": failures,
    }
    return schema


def write_doc(schema: dict[str, Any]) -> None:
    DOC.write_text(
        "\n".join(
            [
                "# Stage10118 True Source-Backed Maintainer Eval Bootstrap Schema",
                "",
                f"Passed: `{schema['passed']}`",
                "",
                schema["decision"],
                "",
                "Evidence role mapping:",
                *[f"- `{role}` -> `{mapped}`" for role, mapped in ROLE_TO_EVIDENCE.items()],
                "",
                f"Next: {schema['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    schema = build()
    write_json(SCHEMA, schema)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": schema["passed"],
        "artifacts": schema["artifacts"],
        "metrics": schema["metrics"],
        "decision": schema["decision"],
        "next_best_step": schema["next_best_step"],
    }
    write_json(SUMMARY, summary)
    write_doc(schema)
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": schema["passed"], "failures": schema["failures"], "metrics": schema["metrics"]}, indent=2, sort_keys=True))
    if schema["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
