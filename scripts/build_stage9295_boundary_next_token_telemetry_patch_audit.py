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
STAGE = 9295
NAME = "stage9295_boundary_next_token_telemetry_patch_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9294_one_next_token_suffix_probe_audit.json"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "boundary_next_token_telemetry_patch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDARY_NEXT_TOKEN_TELEMETRY_PATCH_STAGE9295.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_SNIPPETS = [
    "boundary_next_token",
    "boundary_next_token_logits.jsonl",
    "boundary_next_token_match_rate",
    "boundary_next_token_mean_expected_rank",
    "expected_rank",
    "torch.topk(next_probs",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def audit_patch() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    text = TRAINING_LOOP.read_text(encoding="utf-8") if TRAINING_LOOP.exists() else ""
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9294_not_passed")
    if missing:
        failures.append("boundary_next_token_telemetry_snippets_missing")
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    if metrics.get("quality_gate_passed") is not False:
        failures.append("source_stage9294_did_not_record_quality_failure")
    return {
        "passed": not failures,
        "failures": failures,
        "missing_snippets": missing,
        "source_stage": 9294,
        "source_quality_gate_passed": metrics.get("quality_gate_passed"),
        "records_expected_token_rank": "expected_rank" in text and "expected_probability" in text,
        "records_top_k": "torch.topk(next_probs" in text and "top_k" in text,
        "writes_boundary_logits_artifact": "boundary_next_token_logits.jsonl" in text,
        "sample_generation_card_has_boundary_metrics": "boundary_next_token_match_rate" in text,
        "execution_authorized_next": False,
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_patch()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Added boundary next-token logit/rank telemetry to generation audit after the one-token free-run failure.",
        "next_best_step": "Build a final pre-execution audit for rerunning the tiny one-next-token probe with boundary_next_token_logits.jsonl required, then execute under trellis.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9295 Boundary Next-Token Telemetry Patch",
        "",
        f"Passed: `{audit['passed']}`",
        f"Writes boundary logits artifact: `{audit['writes_boundary_logits_artifact']}`",
        f"Records expected rank: `{audit['records_expected_token_rank']}`",
        f"Records top-k: `{audit['records_top_k']}`",
        "",
        "No execution authority is opened in this stage.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
