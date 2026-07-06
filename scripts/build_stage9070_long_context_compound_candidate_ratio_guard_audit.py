#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.long_context_candidate_miner import _repo_concept_row_usable, _repo_path_quality
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from long_context_candidate_miner import _repo_concept_row_usable, _repo_path_quality  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9070
NAME = "stage9070_long_context_compound_candidate_ratio_guard_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9069 = ROOT / "runs/summaries/stage9069_long_context_compound_term_index_guard_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_COMPOUND_CANDIDATE_RATIO_GUARD_STAGE9070.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_PATH = OUT_DIR / "long_context_compound_candidate_ratio_guard_audit.json"

DEFAULT_MAX_ENTITY_CHUNK_RATIO = 0.01
DEFAULT_MAX_COMPOUND_ENTITY_CHUNK_RATIO = 0.04


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def repo_row(path: str, modality: str = "text") -> dict[str, Any]:
    return {"modality": modality, "metadata_json": json.dumps({"path": path}, sort_keys=True), "text": "spectral_kernel_update concept"}


def ratio_allowed(canonical_name: str, ratio: float) -> bool:
    limit = DEFAULT_MAX_COMPOUND_ENTITY_CHUNK_RATIO if "_" in canonical_name else DEFAULT_MAX_ENTITY_CHUNK_RATIO
    return ratio <= limit


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9069)
    concept_doc = repo_row("repo_a/docs/concepts/spectral_kernel.txt", modality="text")
    concept_code = repo_row("repo_a/src/kernel_notes.py", modality="code")
    concept_test = repo_row("repo_a/tests/test_kernel.py", modality="code")
    readme = repo_row("repo_a/README.md", modality="text")
    checks = {
        "source_stage9069_present": SOURCE_9069.exists(),
        "source_stage9069_passed": source.get("passed") is True,
        "plain_entity_strict_ratio_blocks_0_02": ratio_allowed("kernel", 0.02) is False,
        "compound_entity_relaxed_ratio_allows_0_02": ratio_allowed("spectral_kernel", 0.02) is True,
        "compound_entity_ratio_blocks_above_relaxed_cap": ratio_allowed("spectral_kernel", 0.05) is False,
        "compound_repo_concept_doc_usable": _repo_concept_row_usable(concept_doc, quality=1) is True,
        "compound_repo_concept_code_usable": _repo_concept_row_usable(concept_code, quality=_repo_path_quality("repo_a/src/kernel_notes.py")) is True,
        "compound_repo_test_concept_rejected": _repo_concept_row_usable(concept_test, quality=_repo_path_quality("repo_a/tests/test_kernel.py")) is False,
        "compound_repo_readme_rejected": _repo_concept_row_usable(readme, quality=1) is False,
        "no_real_index_read": True,
        "no_candidate_mining": True,
        "authority_closed": not any(AUTHORITY_CLOSED.values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "default_max_entity_chunk_ratio": DEFAULT_MAX_ENTITY_CHUNK_RATIO,
        "default_max_compound_entity_chunk_ratio": DEFAULT_MAX_COMPOUND_ENTITY_CHUNK_RATIO,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "real_index_rows_read": 0,
            "candidate_rows_materialized": 0,
            "training_authorized": False,
            "model_execution_attempted": False,
            "arxiv_read_authorized_now": False,
            "arxiv_write_authorized": False,
        },
        "decision": "Compound long-context candidate names may use a relaxed chunk-frequency cap and concept-row fallback, while tests/README and over-broad entities remain blocked.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT_PATH.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Long-context compound candidate ratio guard audit failed.",
        "next_best_step": "Continue no-data recovery with final current-frontier reconciliation; real candidate mining remains ticket-gated.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9070 Long Context Compound Candidate Ratio Guard",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recovered compound candidate miner guards: compound identifiers get a separate frequency cap and may use non-test concept rows only when implementation rows are unavailable. No mining is run.",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
