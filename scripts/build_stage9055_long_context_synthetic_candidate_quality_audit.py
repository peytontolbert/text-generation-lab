#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.long_context_candidate_miner import _canonical_name_ok, _repo_path_quality, _repo_row_usable
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from long_context_candidate_miner import _canonical_name_ok, _repo_path_quality, _repo_row_usable  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9055
NAME = "stage9055_long_context_synthetic_candidate_quality_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9054 = ROOT / "runs/summaries/stage9054_long_context_ticket_controls_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_SYNTHETIC_CANDIDATE_QUALITY_AUDIT_STAGE9055.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "synthetic_candidate_quality_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9054)
    engine_path = "repo_a/src/engine.py"
    translation_path = "repo_a/src/assets/translations/lesson.json"
    lockfile_path = "repo_a/package-lock.json"
    engine_row = {"source_type": "repo", "modality": "code", "text": "def online_update():\n    return 'streaming update active'\n"}
    translation_row = {"source_type": "repo", "modality": "structured_data", "text": '{"title":"Streaming update lesson"}'}
    lockfile_row = {"source_type": "repo", "modality": "structured_data", "text": '{"name":"lock"}'}
    engine_quality = _repo_path_quality(engine_path)
    translation_quality = _repo_path_quality(translation_path)
    lockfile_quality = _repo_path_quality(lockfile_path)
    checks = {
        "source_stage9054_present": SOURCE_9054.exists(),
        "source_stage9054_passed": source.get("passed") is True,
        "semantic_entity_kept": _canonical_name_ok("streaming_update"),
        "generic_entity_rejected": not _canonical_name_ok("state"),
        "engine_quality_positive": engine_quality > 1,
        "translation_quality_lower_than_engine": translation_quality < engine_quality,
        "lockfile_quality_lower_than_engine": lockfile_quality < engine_quality,
        "engine_row_usable": _repo_row_usable(engine_row, quality=engine_quality),
        "translation_row_rejected": not _repo_row_usable(translation_row, quality=translation_quality),
        "lockfile_row_rejected": not _repo_row_usable(lockfile_row, quality=lockfile_quality),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "quality_scores": {
            engine_path: engine_quality,
            translation_path: translation_quality,
            lockfile_path: lockfile_quality,
        },
        "repo_evidence_paths": [engine_path],
        "candidate_count": 1 if checks["engine_row_usable"] else 0,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "synthetic_fixture_only": True,
            "pyarrow_required": False,
            "fixture_chunks": 0,
            "fixture_entities": 0,
            "fixture_links": 0,
            "candidate_count": 1 if checks["engine_row_usable"] else 0,
            "repo_evidence_paths": 1 if checks["engine_row_usable"] else 0,
            "real_corpus_scan_authorized_now": False,
            "arxiv_read_authorized_now": False,
            "arxiv_write_authorized": False,
            "hf_upload_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
        },
        "decision": "Synthetic candidate quality/routing audit passed: code-like repo evidence is usable while translation assets, lockfiles, and generic entities are rejected.",
    }

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Synthetic candidate quality/routing audit failed.",
        "next_best_step": "If staying no-data, add a synthetic compiler route-card audit for long-context candidates. Real candidate mining still requires a separate granted source/output ticket.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9055 Long Context Synthetic Candidate Quality Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage uses only repo-local synthetic fixtures. It does not read `/arxiv`, scan real corpora, upload to Hugging Face, execute a model, or train.",
        "",
        f"Candidate rows: `{audit['candidate_count']}`",
        "",
        "Repo evidence paths:",
        "",
        *[f"- `{path}`" for path in audit["repo_evidence_paths"]],
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
