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
STAGE = 9642
NAME = "stage9642_per_head_probe_failure_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9641_per_head_boundary_prefix_observe_tiny_probe.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9641_per_head_boundary_prefix_observe_tiny_probe/per_head_boundary_prefix_observe_tiny_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9640_per_head_boundary_prefix_observe_manifest/per_head_boundary_prefix_observe_manifest.jsonl"
LOGITS = ROOT / "runs/local/artifacts/stage9641_per_head_boundary_prefix_observe_tiny_probe/episode_step_probe/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "per_head_probe_failure_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PER_HEAD_PROBE_FAILURE_AUDIT_STAGE9642.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def obs(row: dict[str, Any]) -> dict[str, Any]:
    tr = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    return tr.get("observation_t") if isinstance(tr.get("observation_t"), dict) else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    source_audit = load_json(SOURCE_AUDIT)
    rows = load_jsonl(MANIFEST)
    logits = load_jsonl(LOGITS)
    by_id = {row.get("row_id"): row for row in rows}

    label_by_split: dict[str, dict[str, dict[str, int]]] = {}
    for split in ["train", "eval", "strict_eval"]:
        split_rows = [row for row in rows if row.get("split") == split]
        label_by_split[split] = {
            "episode_boundary_match": dict(Counter(str(obs(row).get("boundary_next_token_match")) for row in split_rows)),
            "episode_target_prefix_match": dict(Counter(str(obs(row).get("target_prefix_match")) for row in split_rows)),
        }

    wrong = [row for row in logits if row.get("correct") is False]
    wrong_pairs = Counter(f"{row.get('split')}::{row.get('field')}::{row.get('target')}=>{row.get('pred')}" for row in wrong)
    wrong_source_rows = Counter(str(row.get("row_id")) for row in wrong)
    wrong_source_families = Counter()
    for row_id in wrong_source_rows:
        manifest_row = by_id.get(row_id)
        if manifest_row:
            source_id = str(manifest_row.get("source_stage9637_row_id") or "")
            if source_id.startswith("stage9637_counterpositive") or source_id.startswith("stage9634_counterpositive"):
                wrong_source_families["counterpositive"] += 1
            elif source_id.startswith("stage9637_counternegative"):
                wrong_source_families["counternegative"] += 1
            else:
                wrong_source_families["base"] += 1

    failures: list[str] = []
    if source.get("passed") is not False:
        failures.append("stage9641_was_not_quality_failure")
    if source_audit.get("safety_passed") is not True:
        failures.append("stage9641_safety_not_clean")
    if not rows or not logits:
        failures.append("missing_inputs")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "label_by_split": label_by_split,
        "wrong_pairs": dict(wrong_pairs.most_common(20)),
        "wrong_source_families": dict(wrong_source_families),
        "high_confidence_wrong_rows": source_audit.get("high_confidence_wrong_rows"),
        "strict_field_exact": source_audit.get("strict_field_exact"),
        "diagnosis": (
            "The isolated two-head probe still learned a high-confidence false default. "
            "Train/eval were prefix-negative heavy while strict was positive-heavy, so strict positives failed as true=>false. "
            "The next manifest should balance true/false labels per split for both boundary and prefix, with counterpositive rows present in train/eval/strict."
        ),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Build Stage9643 balanced-positive per-head observe manifest with true/false labels balanced per split "
        "for episode_boundary_match and episode_target_prefix_match; run contract/shortcut audit before another tiny probe."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9641 failed safely; the next patch is split-balanced positive supervision, not more mixed heads.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9642 Per-Head Probe Failure Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Strict field exact: `{audit['strict_field_exact']}`",
                f"High-confidence wrong rows: `{audit['high_confidence_wrong_rows']}`",
                f"Label by split: `{label_by_split}`",
                f"Top wrong pairs: `{dict(wrong_pairs.most_common(10))}`",
                "",
                audit["diagnosis"],
                "",
                "Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
