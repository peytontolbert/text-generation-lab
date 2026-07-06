#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9042
NAME = "stage9042_long_context_corpus_index_guard_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9038 = ROOT / "runs/summaries/stage9038_long_context_no_data_scan_ticket.json"
SOURCE_9039 = ROOT / "runs/summaries/stage9039_long_context_relation_graph_readiness.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_CORPUS_INDEX_GUARD_STAGE9042.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "long_context_corpus_index_guard_audit.json"
BUILDER = ROOT / "scripts/build_stage8801_long_context_corpus_index.py"
PARQUET_HELPER = ROOT / "scripts/long_context_parquet.py"
SPEC = ROOT / "docs/LONG_CONTEXT_TRANSITION_DATASET_SPEC.md"
TEST = ROOT / "tests/test_long_context_transition_pipeline.py"

REQUIRED_GUARDS = [
    "--allow-corpus-scan",
    "--allow-arxiv-output",
    "validate_corpus_index_request",
    "CorpusIndexSafetyError",
    "FORBIDDEN_CORPUS_ROOTS",
]
FORBIDDEN_DEFAULT_AUTHORITY = [
    "corpus_index_executed_now",
    "arxiv_scan_authorized_now",
    "repository_library_scan_authorized_now",
    "parquet_written_now",
    "hf_upload_authorized_now",
    "training_rows_materialized_now",
    "data_mining_authorized",
    "training_authorized",
    "model_execution_attempted",
    "arxiv_write_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    builder_text = text(BUILDER)
    spec_text = text(SPEC)
    test_text = text(TEST)
    source_9038 = load_json(SOURCE_9038)
    source_9039 = load_json(SOURCE_9039)
    checks = {
        "source_stage9038_present": SOURCE_9038.exists(),
        "source_stage9038_passed": source_9038.get("passed") is True,
        "source_stage9039_present": SOURCE_9039.exists(),
        "source_stage9039_passed": source_9039.get("passed") is True,
        "builder_present": BUILDER.exists(),
        "parquet_helper_present": PARQUET_HELPER.exists(),
        "all_required_guards_present": all(item in builder_text for item in REQUIRED_GUARDS),
        "spec_marks_arxiv_as_future_gated": "not currently authorize production scans or `/arxiv` writes" in spec_text,
        "spec_mentions_required_flags": "--allow-corpus-scan" in spec_text and "--allow-arxiv-output" in spec_text,
        "test_covers_default_refusal": "test_production_parquet_index_requires_explicit_corpus_scan_flag" in test_text,
        "test_uses_tmp_path_for_parquet_write": "tmp_path / \"parquet_out\"" in test_text or "tmp_path / 'parquet_out'" in test_text,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    metrics = {
        **{key: False for key in FORBIDDEN_DEFAULT_AUTHORITY},
        "guarded_builder_files": 2,
        "required_guards": len(REQUIRED_GUARDS),
        "forbidden_default_authority_flags": len(FORBIDDEN_DEFAULT_AUTHORITY),
        "corpus_index_guard_audit_only": True,
        "fixture_only_parquet_test_allowed": True,
        "production_corpus_index_authorized_now": False,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LONG_CONTEXT_CORPUS_INDEX_GUARD_AUDIT_NO_EXECUTION",
        "required_guards": REQUIRED_GUARDS,
        "forbidden_default_authority": FORBIDDEN_DEFAULT_AUTHORITY,
        "checks": checks,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Preserve the Parquet corpus-index utilities, but keep production corpus scans, /arxiv writes, HF upload, mining, and training closed until a later explicit gate authorizes them.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in FORBIDDEN_DEFAULT_AUTHORITY + ["production_corpus_index_authorized_now"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("fixture_only_parquet_test_allowed") is not True:
        failures.append("fixture_test_not_marked_allowed")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"guard_audit": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Keep corpus indexing closed. If needed, design a separate active corpus-root ticket before scanning /arxiv, repository_library, writing Parquet under /arxiv, or uploading to Hugging Face.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9042 Long Context Corpus Index Guard Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage preserves the long-context Parquet corpus-index utilities as guarded infrastructure only.",
        "Production corpus scans, `/arxiv` writes, Hugging Face uploads, mining, model execution, decoder CE, and training remain closed.",
        "",
        "Required CLI guards:",
        "",
        *[f"- `{item}`" for item in REQUIRED_GUARDS],
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
