#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9213
NAME = "stage9213_repo_local_execution_review_matrix_after_adapters"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9212 = ROOT / "runs/summaries/stage9212_repo_local_tiny_cap_adapter_audit.json"
SOURCE_9208_MATRIX = ROOT / "runs/local/artifacts/stage9208_repo_local_execution_review_matrix/repo_local_execution_review_matrix.json"
SOURCE_9211_INDEX = ROOT / "runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/repo_local_tiny_cap_adapter_index.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_EXECUTION_REVIEW_MATRIX_AFTER_ADAPTERS_STAGE9213.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "repo_local_execution_review_matrix_after_adapters.json"

AUTHORIZATION_SOURCES = {
    "structured_policy_probe": ROOT / "runs/summaries/stage8882_tiny_structured_probe_execution_authorization_review.json",
    "bounded_decoder_ce_probe": ROOT / "runs/summaries/stage8956_bounded_decoder_future_one_run_authorization_schema.json",
    "denoise_repair_probe": ROOT / "runs/summaries/stage8884_no_execution_denoise_authorization_review.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def old_review(matrix: dict[str, Any], mode: str) -> dict[str, Any]:
    for item in matrix.get("family_reviews") or []:
        if item.get("mode") == mode:
            return item
    return {}


def adapter(index: dict[str, Any], mode: str) -> dict[str, Any]:
    for item in index.get("adapters") or []:
        if item.get("mode") == mode:
            return item
    return {}


def path_is_repo_local(path_text: str) -> bool:
    if not path_text or "/arxiv" in path_text:
        return False
    try:
        (ROOT / path_text).resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def adapted_review(mode: str, source: dict[str, Any], auth_sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    if not source:
        failures.append("source_missing")
    source_passed = source.get("passed") is True or (
        source.get("status") == "future_review_candidate" and not source.get("review_failures")
    )
    if not source_passed:
        failures.append("source_not_passed")
    output_manifest = str(source.get("output_manifest") or source.get("manifest_path") or "")
    if output_manifest and not path_is_repo_local(output_manifest):
        failures.append("manifest_not_repo_local")
    if auth_sources.get(mode, {}).get("passed") is not True:
        failures.append(f"authorization_source_not_passed:{mode}")
    if mode == "denoise_repair_probe":
        failures.append("dedicated_one_run_ticket_schema_missing")

    if failures:
        status = "requires_dedicated_one_run_ticket_schema" if mode == "denoise_repair_probe" else "blocked_until_review_failures_resolved"
    else:
        status = "future_review_candidate"
    return {
        "mode": mode,
        "status": status,
        "manifest_path": output_manifest,
        "review_failures": failures,
        "authorization_source_passed": bool(auth_sources.get(mode, {}).get("passed")),
        "same_stage_execution_authorized": False,
        "next_stage_execution_authorized": False,
    }


def build_matrix() -> dict[str, Any]:
    source_9212 = load_json(SOURCE_9212)
    old_matrix = load_json(SOURCE_9208_MATRIX)
    adapter_index = load_json(SOURCE_9211_INDEX)
    auth_sources = {name: load_json(path) for name, path in AUTHORIZATION_SOURCES.items()}
    reviews = [
        adapted_review("structured_policy_probe", old_review(old_matrix, "structured_policy_probe"), auth_sources),
        adapted_review("bounded_decoder_ce_probe", adapter(adapter_index, "bounded_decoder_ce_probe"), auth_sources),
        adapted_review("denoise_repair_probe", adapter(adapter_index, "denoise_repair_probe"), auth_sources),
    ]
    candidate_modes = [item["mode"] for item in reviews if item["status"] == "future_review_candidate"]
    checks = {
        "source_stage9212_passed": source_9212.get("passed") is True,
        "old_matrix_passed": old_matrix.get("passed") is True,
        "adapter_index_passed": adapter_index.get("passed") is True,
        "three_family_reviews_written": len(reviews) == 3,
        "structured_future_candidate": "structured_policy_probe" in candidate_modes,
        "bounded_decoder_future_candidate": "bounded_decoder_ce_probe" in candidate_modes,
        "denoise_still_schema_blocked": any(
            item["mode"] == "denoise_repair_probe" and item["status"] == "requires_dedicated_one_run_ticket_schema"
            for item in reviews
        ),
        "same_stage_execution_closed": True,
        "next_stage_execution_closed": True,
        "all_authority_closed": True,
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
        "family_reviews": reviews,
        "future_review_candidates": candidate_modes,
        "decision": (
            "After tiny-cap adapters, structured-policy and bounded decoder are future review candidates. "
            "Denoise caps are fixed, but it still needs a dedicated one-run ticket schema. No execution is authorized."
        ),
        "next_best_step": (
            "Choose the next no-execution branch: bounded-decoder inactive ticket design, denoise dedicated ticket schema, "
            "or stop before any final pre-execution audit until explicit execution is requested."
        ),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    matrix = build_matrix()
    MATRIX.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": matrix["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": matrix["failures"],
            "family_reviews": len(matrix["family_reviews"]),
            "future_review_candidates": len(matrix["future_review_candidates"]),
            "same_stage_execution_authorized": False,
            "next_stage_execution_authorized": False,
            "trainer_executed_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "cleanup_authorized_now": False,
        },
        "artifacts": {
            "matrix": str(MATRIX.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": matrix["decision"] if matrix["passed"] else "Repo-local execution review matrix refresh failed.",
        "next_best_step": matrix["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9213 Repo-Local Execution Review Matrix After Adapters",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage refreshes the no-execution review matrix after Stage9211/9212 tiny-cap adapters.",
                "It does not run trainer, execute a model, clean outputs, touch /arxiv, or open decoder/denoise CE authority.",
                "",
                f"Future review candidates: `{summary['metrics']['future_review_candidates']}`",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
