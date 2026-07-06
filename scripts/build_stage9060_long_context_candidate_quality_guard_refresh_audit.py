#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.long_context_candidate_miner import (
        _canonical_name_ok,
        _entity_specificity_score,
        _entity_support_ok,
        _repo_path_quality,
        _repo_row_sort_key,
        _repo_row_usable,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from long_context_candidate_miner import (  # type: ignore
        _canonical_name_ok,
        _entity_specificity_score,
        _entity_support_ok,
        _repo_path_quality,
        _repo_row_sort_key,
        _repo_row_usable,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9060
NAME = "stage9060_long_context_candidate_quality_guard_refresh_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9059 = ROOT / "runs/summaries/stage9059_long_context_route_card_materialization_audit_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_CANDIDATE_QUALITY_GUARD_REFRESH_STAGE9060.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_PATH = OUT_DIR / "candidate_quality_guard_refresh_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def repo_row(path: str, text: str, *, source_id: str = "repo_a", doc_id: str | None = None) -> dict[str, Any]:
    return {
        "source_type": "repo",
        "source_id": source_id,
        "doc_id": doc_id or path,
        "modality": "code",
        "text": text,
        "metadata_json": json.dumps({"path": path}, sort_keys=True),
    }


def paper_row(path: str, text: str, *, source_id: str = "paper_a", doc_id: str | None = None) -> dict[str, Any]:
    return {
        "source_type": "paper",
        "source_id": source_id,
        "doc_id": doc_id or path,
        "modality": "paper_text",
        "text": text,
        "metadata_json": json.dumps({"path": path}, sort_keys=True),
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9059)
    src_impl = repo_row("repo_a/src/engine.py", "def spectral_kernel_update(x):\n    return x\n", source_id="repo_a")
    pkg_impl = repo_row("repo_b/pkg/kernel.go", "func SpectralKernelUpdate() int { return 1 }\n", source_id="repo_b")
    test_row = repo_row("repo_a/tests/test_engine.py", "def test_spectral_kernel_update():\n    assert spectral_kernel_update(1) == 1\n")
    translation_row = repo_row("repo_a/assets/translations/en.ts", "export const spectralKernel = 'label'\n")
    lock_row = repo_row("repo_a/package-lock.json", "spectral_kernel_update\n")
    paper_a = paper_row("paper_a/method.txt", "The spectral_kernel method stabilizes update transitions.", source_id="paper_a")
    paper_b = paper_row("paper_b/results.txt", "Spectral_kernel improves benchmark stability.", source_id="paper_b")
    supported_rows = [src_impl, pkg_impl, paper_a, paper_b]
    under_supported_rows = [src_impl, paper_a]
    scored_repo_rows = [
        (_repo_path_quality(json.loads(row["metadata_json"])["path"]), row)
        for row in [test_row, src_impl, translation_row, pkg_impl, lock_row]
    ]
    sorted_paths = [
        json.loads(row["metadata_json"])["path"]
        for quality, row in sorted(scored_repo_rows, key=lambda item: _repo_row_sort_key(item[1], quality=item[0]))
    ]
    checks = {
        "source_stage9059_present": SOURCE_9059.exists(),
        "source_stage9059_passed": source.get("passed") is True,
        "generic_names_rejected": all(not _canonical_name_ok(name) for name in ["state", "append", "torch", "dataset", "research"]),
        "specific_candidate_name_kept": _canonical_name_ok("spectral_kernel"),
        "single_source_mentions_do_not_pass_support": _entity_support_ok(under_supported_rows, ("paper", "repo")) is False,
        "multi_source_mentions_pass_support": _entity_support_ok(supported_rows, ("paper", "repo")) is True,
        "specificity_positive_for_cross_source_entity": _entity_specificity_score("spectral_kernel", supported_rows) >= 1,
        "implementation_path_scores_above_tests": _repo_path_quality("repo_a/src/engine.py") > _repo_path_quality("repo_a/tests/test_engine.py"),
        "implementation_paths_sort_first": sorted_paths[:2] == ["repo_a/src/engine.py", "repo_b/pkg/kernel.go"],
        "translation_asset_not_usable": _repo_row_usable(translation_row, quality=_repo_path_quality("repo_a/assets/translations/en.ts")) is False,
        "lockfile_not_usable": _repo_row_usable(lock_row, quality=_repo_path_quality("repo_a/package-lock.json")) is False,
        "test_row_not_usable_as_primary_evidence": _repo_row_usable(test_row, quality=_repo_path_quality("repo_a/tests/test_engine.py")) is False,
        "implementation_row_usable": _repo_row_usable(src_impl, quality=_repo_path_quality("repo_a/src/engine.py")) is True,
        "no_real_index_read": True,
        "no_candidate_materialization": True,
        "authority_closed": not any(AUTHORITY_CLOSED.values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "synthetic_sorted_repo_paths": sorted_paths,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "generic_rejection_terms_checked": 5,
            "real_index_rows_read": 0,
            "candidate_rows_materialized": 0,
            "training_authorized": False,
            "model_execution_attempted": False,
            "arxiv_read_authorized_now": False,
            "arxiv_write_authorized": False,
        },
        "decision": "Long-context candidate miner quality guards prefer implementation evidence, reject noisy/generic entities, and remain no-data/no-training.",
    }


def write_outputs(audit: dict[str, Any]) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT_PATH.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Long-context candidate quality guard refresh failed.",
        "next_best_step": "Continue trainer/compiler no-data recovery; future compiler handoff must require route-card materialization and all gate artifacts before any gradients.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9060 Long Context Candidate Quality Guard Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This no-data audit records recovered candidate-miner guards: generic names are rejected, cross-source support is required, and implementation code rows outrank tests/assets/lockfiles as future candidate evidence.",
        "",
        "No `/arxiv` reads or writes, route-card materialization, compiler handoff, model execution, or training were authorized.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
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
    return summary


def main() -> None:
    audit = build_audit()
    summary = write_outputs(audit)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
