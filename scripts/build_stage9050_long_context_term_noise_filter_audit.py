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
STAGE = 9050
NAME = "stage9050_long_context_term_noise_filter_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9042 = ROOT / "runs/summaries/stage9042_long_context_corpus_index_guard_audit.json"
COMMON = ROOT / "scripts/long_context_common.py"
CHUNK_CATALOG = ROOT / "scripts/long_context_chunk_catalog.py"
ENTITY_LINKER = ROOT / "scripts/long_context_entity_linker.py"
CORPUS_INDEX = ROOT / "scripts/build_stage8801_long_context_corpus_index.py"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_TERM_NOISE_FILTER_AUDIT_STAGE9050.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "long_context_term_noise_filter_audit.json"

REQUIRED_TERMS = [
    "GENERIC_CORPUS_TERMS",
    "STRUCTURED_NOISE_TERMS",
    "should_keep_term",
    "source_type",
    "modality",
]
NOISE_EXAMPLES = ["timestamp", "payload", "response_item", "model_provider", "token_count", "source_id"]
KEEP_EXAMPLES = ["retrieval", "verifier", "symbolic", "counterfactual", "regression"]
FORBIDDEN_NOW = [
    "run_corpus_index",
    "scan_arxiv",
    "scan_repository_library",
    "write_parquet_under_arxiv",
    "upload_hf",
    "train_model",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9042 = load_json(SOURCE_9042)
    common = text(COMMON)
    chunk = text(CHUNK_CATALOG)
    linker = text(ENTITY_LINKER)
    corpus = text(CORPUS_INDEX)
    checks = {
        "source_stage9042_present": SOURCE_9042.exists(),
        "source_stage9042_passed": s9042.get("passed") is True,
        "common_has_noise_filter_terms": all(item in common for item in REQUIRED_TERMS[:3]),
        "common_extract_terms_accepts_context": "source_type: str | None" in common and "modality: str | None" in common,
        "chunk_catalog_passes_context": "source_type=source_type" in chunk and "modality=modality_from_suffix(path)" in chunk,
        "entity_linker_passes_context": "source_type=str(chunk.get" in linker and "modality=str(chunk.get" in linker,
        "corpus_index_passes_context": "source_type=source_type" in corpus and "modality=modality_from_suffix(path)" in corpus,
        "corpus_index_has_high_frequency_entity_cap": "max_chunk_frequency_ratio" in corpus,
        "corpus_index_guard_still_present": "--allow-corpus-scan" in corpus and "--allow-arxiv-output" in corpus,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LONG_CONTEXT_TERM_NOISE_FILTER_AUDIT_NO_DATA_SCAN",
        "noise_examples": NOISE_EXAMPLES,
        "keep_examples": KEEP_EXAMPLES,
        "forbidden_now": FORBIDDEN_NOW,
        "checks": checks,
        "metrics": {
            "noise_examples": len(NOISE_EXAMPLES),
            "keep_examples": len(KEEP_EXAMPLES),
            "high_frequency_entity_cap_recorded": True,
            "term_filter_audit_only": True,
            "corpus_index_executed_now": False,
            "arxiv_scan_authorized_now": False,
            "repository_library_scan_authorized_now": False,
            "parquet_written_now": False,
            "hf_upload_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Preserve source/modality-aware term-noise filtering for long-context indexing while keeping corpus scans, Parquet writes, HF upload, and training closed.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "corpus_index_executed_now",
        "arxiv_scan_authorized_now",
        "repository_library_scan_authorized_now",
        "parquet_written_now",
        "hf_upload_authorized_now",
        "training_authorized",
        "model_execution_attempted",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
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
        "artifacts": {"audit": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Keep long-context indexing in guarded fixture mode. Real corpus indexing still requires a separate active source/output ticket.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9050 Long Context Term Noise Filter Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage preserves source/modality-aware term-noise filtering for long-context indexing.",
        "It does not run corpus indexing, scan `/arxiv`, write Parquet, upload to Hugging Face, execute a model, or train.",
        "",
        "Noise examples:",
        "",
        *[f"- `{item}`" for item in NOISE_EXAMPLES],
        "",
        "Keep examples:",
        "",
        *[f"- `{item}`" for item in KEEP_EXAMPLES],
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
