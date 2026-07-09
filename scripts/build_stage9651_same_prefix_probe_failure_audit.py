#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9651
NAME = "stage9651_same_prefix_probe_failure_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9650_same_prefix_contrast_tiny_probe.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9650_same_prefix_contrast_tiny_probe/same_prefix_contrast_tiny_probe_audit.json"
LOGITS = ROOT / "runs/local/artifacts/stage9650_same_prefix_contrast_tiny_probe/episode_step_probe/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "same_prefix_probe_failure_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SAME_PREFIX_PROBE_FAILURE_AUDIT_STAGE9651.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    audit_in = load_json(SOURCE_AUDIT)
    logits = load_jsonl(LOGITS)
    failures: list[str] = []
    if source.get("passed") is not False:
        failures.append("stage9650_was_not_quality_failure")
    if audit_in.get("safety_passed") is not True:
        failures.append("stage9650_safety_not_clean")
    if not logits:
        failures.append("missing_logits")
    pred_pairs = Counter(f"{row.get('split')}::{row.get('field')}::{row.get('target')}=>{row.get('pred')}" for row in logits if row.get("correct") is False)
    confidence_bins = Counter("high" if float(row.get("confidence") or 0) >= 0.9 else ("medium" if float(row.get("confidence") or 0) >= 0.6 else "low") for row in logits)
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "wrong_pairs": dict(pred_pairs.most_common(20)),
        "confidence_bins": dict(confidence_bins),
        "decoder_delta_norm": audit_in.get("decoder_delta_norm"),
        "strict_field_exact": audit_in.get("strict_field_exact"),
        "diagnosis": "Same-prefix contrast removed prefix identity as a shortcut, but target-100M stayed at chance with low confidence. The representation likely needs an explicit structured boundary_token_relation feature instead of asking the tiny probe to infer equality from two serialized text fields.",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9652 comparator-feature micro manifest with boundary_token_relation=same|different, then run contract audit before execution."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Stage9650 failed safely; add an explicit structured comparator feature before another probe.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9651 Same-Prefix Probe Failure Audit", "", f"Passed: `{audit['passed']}`", f"Strict field exact: `{audit['strict_field_exact']}`", f"Confidence bins: `{dict(confidence_bins)}`", f"Top wrong pairs: `{dict(pred_pairs.most_common(10))}`", "", audit["diagnosis"], "", "Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
