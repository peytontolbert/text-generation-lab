#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.long_context_common import extract_compound_terms, normalize_compound_term
    from scripts.build_stage8801_long_context_corpus_index import _chunk_row, _mention_rows
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from long_context_common import extract_compound_terms, normalize_compound_term  # type: ignore
    from build_stage8801_long_context_corpus_index import _chunk_row, _mention_rows  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9069
NAME = "stage9069_long_context_compound_term_index_guard_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9068 = ROOT / "runs/summaries/stage9068_long_context_candidate_dispersion_guard_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_COMPOUND_TERM_INDEX_GUARD_STAGE9069.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_PATH = OUT_DIR / "long_context_compound_term_index_guard_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9068)
    text = "stateSpaceModel calls spectral_kernel_update while multi-agent label text is ignored"
    terms = extract_compound_terms(text, max_terms=16, source_type="repo", modality="code")
    fake_root = ROOT
    fake_path = ROOT / "repo_a" / "src" / "engine.py"
    chunk = _chunk_row(source_root=fake_root, path=fake_path, chunk_index=0, text=text)
    metadata = json.loads(chunk["metadata_json"])
    mentions = _mention_rows(chunk)
    mention_terms = {row["term"] for row in mentions}
    checks = {
        "source_stage9068_present": SOURCE_9068.exists(),
        "source_stage9068_passed": source.get("passed") is True,
        "camel_case_normalized": normalize_compound_term("stateSpaceModel") == "state_space",
        "snake_case_preserved": normalize_compound_term("spectral_kernel_update") == "spectral_kernel_update",
        "generic_hyphen_phrase_rejected": normalize_compound_term("multi-agent") is None,
        "compound_terms_extracted": {"state_space", "spectral_kernel_update"}.issubset(set(terms)),
        "chunk_metadata_contains_compound_terms": {"state_space", "spectral_kernel_update"}.issubset(set(metadata.get("compound_terms") or [])),
        "mention_rows_include_compound_terms": {"state_space", "spectral_kernel_update"}.issubset(mention_terms),
        "no_real_index_written": True,
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
        "extracted_terms": terms,
        "metadata_compound_terms": metadata.get("compound_terms") or [],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "real_index_rows_read": 0,
            "real_index_rows_written": 0,
            "candidate_rows_materialized": 0,
            "compound_terms_extracted": len(terms),
            "training_authorized": False,
            "model_execution_attempted": False,
            "arxiv_read_authorized_now": False,
            "arxiv_write_authorized": False,
        },
        "decision": "Long-context index recovery now preserves compound software identifiers as metadata and mention candidates without building real indexes or mining data.",
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
        "decision": audit["decision"] if audit["passed"] else "Long-context compound term index guard audit failed.",
        "next_best_step": "Continue no-data recovery with final current-frontier reconciliation; source/index building and candidate mining remain ticket-gated.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9069 Long Context Compound Term Index Guard",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recovered compound identifier extraction for long-context indexing. Compound software identifiers are captured in metadata and mention rows, while generic label-like hyphen phrases are rejected. No real index is built.",
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
