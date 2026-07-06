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
STAGE = 9051
NAME = "stage9051_long_context_candidate_miner_guard_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9050 = ROOT / "runs/summaries/stage9050_long_context_term_noise_filter_audit.json"
MINER = ROOT / "scripts/long_context_candidate_miner.py"
SPEC = ROOT / "docs/LONG_CONTEXT_TRANSITION_DATASET_SPEC.md"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_CANDIDATE_MINER_GUARD_AUDIT_STAGE9051.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "long_context_candidate_miner_guard_audit.json"

REQUIRED_MINER_TERMS = [
    "CandidateMiningSafetyError",
    "validate_candidate_mining_request",
    "--allow-candidate-mining",
    "--allow-arxiv-output",
    "allow_candidate_mining_flag",
    "arxiv_output_requires_explicit_output_flag",
]
FORBIDDEN_NOW = [
    "run_candidate_mining",
    "read_arxiv_index",
    "write_candidates_under_arxiv",
    "upload_hf",
    "train_model",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9050 = load_json(SOURCE_9050)
    miner = read(MINER)
    spec = read(SPEC)
    authority_counts = ((registry.get("metrics") or {}).get("authority_counts") or {})
    checks = {
        "source_stage9050_present": SOURCE_9050.exists(),
        "source_stage9050_passed": s9050.get("passed") is True,
        "candidate_miner_present": MINER.exists(),
        "candidate_miner_has_guard_terms": all(term in miner for term in REQUIRED_MINER_TERMS),
        "candidate_miner_validates_before_mining": "validate_candidate_mining_request(" in miner and miner.find("validate_candidate_mining_request(") < miner.find("candidates, summary = mine_candidates("),
        "candidate_mining_docs_mark_future_gate": "Candidate mining from `/arxiv` remains future-gated" in spec,
        "candidate_mining_docs_show_required_flags": "--allow-candidate-mining" in spec and "--allow-arxiv-output" in spec,
        "authority_counts_zero": not any(authority_counts.get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LONG_CONTEXT_CANDIDATE_MINER_GUARD_AUDIT_NO_MINING",
        "checks": checks,
        "forbidden_now": FORBIDDEN_NOW,
        "metrics": {
            "candidate_miner_guard_audit_only": True,
            "candidate_mining_executed_now": False,
            "arxiv_index_read_authorized_now": False,
            "arxiv_candidate_write_authorized_now": False,
            "hf_upload_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Preserve the candidate miner, but require explicit future source/output authorization before reading real long-context indexes or writing candidates under /arxiv.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "candidate_mining_executed_now",
        "arxiv_index_read_authorized_now",
        "arxiv_candidate_write_authorized_now",
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
        "next_best_step": "Design an active source/output ticket for a tiny explicit long-context index only if real candidate mining is needed. Otherwise continue pipeline recovery without data scans.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9051 Long Context Candidate Miner Guard Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records that candidate mining is guarded. It does not read a real index, scan `/arxiv`, write candidates, upload to Hugging Face, execute a model, or train.",
        "",
        "Required future CLI gates:",
        "",
        "- `--allow-candidate-mining`",
        "- `--allow-arxiv-output` when output is under `/arxiv`",
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
