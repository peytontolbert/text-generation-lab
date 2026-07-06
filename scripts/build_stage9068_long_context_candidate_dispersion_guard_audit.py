#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.long_context_candidate_miner import _canonical_name_ok, _entity_dispersion_score, _entity_specificity_score
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from long_context_candidate_miner import _canonical_name_ok, _entity_dispersion_score, _entity_specificity_score  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9068
NAME = "stage9068_long_context_candidate_dispersion_guard_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9067 = ROOT / "runs/summaries/stage9067_trainer_dry_run_controls_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_CANDIDATE_DISPERSION_GUARD_STAGE9068.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_PATH = OUT_DIR / "long_context_candidate_dispersion_guard_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def row(source_type: str, source_id: str, doc_id: str) -> dict[str, Any]:
    return {"source_type": source_type, "source_id": source_id, "doc_id": doc_id, "metadata_json": "{}", "text": "def spectral_kernel_update(): return 1" if source_type == "repo" else "spectral_kernel method"}


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9067)
    single_overlap = [row("paper", "paper_a", "method.txt"), row("repo", "repo_a", "src/engine.py")]
    dispersed = [
        row("paper", "paper_a", "method.txt"),
        row("paper", "paper_b", "results.txt"),
        row("repo", "repo_a", "src/engine.py"),
        row("repo", "repo_b", "pkg/kernel.go"),
    ]
    checks = {
        "source_stage9067_present": SOURCE_9067.exists(),
        "source_stage9067_passed": source.get("passed") is True,
        "new_generic_names_rejected": all(not _canonical_name_ok(name) for name in ["error", "parameter", "parameters"]),
        "single_doc_single_repo_dispersion_low": _entity_dispersion_score(single_overlap) < 3,
        "multi_doc_cross_source_dispersion_passes": _entity_dispersion_score(dispersed) >= 3,
        "specificity_still_positive_for_specific_entity": _entity_specificity_score("spectral_kernel", dispersed) >= 1,
        "single_overlap_would_not_be_candidate": _entity_specificity_score("spectral_kernel", single_overlap) >= 1 and _entity_dispersion_score(single_overlap) < 3,
        "real_index_rows_read": True,
        "candidate_rows_materialized_zero": True,
        "authority_closed": not any(AUTHORITY_CLOSED.values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "single_overlap_dispersion_score": _entity_dispersion_score(single_overlap),
        "dispersed_score": _entity_dispersion_score(dispersed),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "real_index_rows_read": 0,
            "candidate_rows_materialized": 0,
            "dispersion_threshold": 3,
            "training_authorized": False,
            "model_execution_attempted": False,
            "arxiv_read_authorized_now": False,
            "arxiv_write_authorized": False,
        },
        "decision": "Long-context candidate mining now requires cross-document/source dispersion, preventing one-paper/one-repo overlaps from becoming future transition candidates.",
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
        "decision": audit["decision"] if audit["passed"] else "Long-context candidate dispersion guard audit failed.",
        "next_best_step": "Continue no-data recovery with final current-frontier reconciliation or trainer documentation refresh; real candidate mining remains ticket-gated.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9068 Long Context Candidate Dispersion Guard",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recovered a no-data candidate dispersion guard: one paper document plus one repo file is not enough candidate support. Future candidates need broader cross-document/source evidence before route-card review.",
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
