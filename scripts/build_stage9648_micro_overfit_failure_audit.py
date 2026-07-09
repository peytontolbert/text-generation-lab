#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9648
NAME = "stage9648_micro_overfit_failure_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9647_micro_overfit_boundary_prefix_tiny_probe.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9647_micro_overfit_boundary_prefix_tiny_probe/micro_overfit_boundary_prefix_tiny_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9646_micro_overfit_boundary_prefix_manifest/micro_overfit_boundary_prefix_manifest.jsonl"
LOGITS = ROOT / "runs/local/artifacts/stage9647_micro_overfit_boundary_prefix_tiny_probe/episode_step_probe/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "micro_overfit_failure_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MICRO_OVERFIT_FAILURE_AUDIT_STAGE9648.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def obs(row: dict[str, Any]) -> dict[str, Any]:
    return row["episode_transition"]["observation_t"]


def state(row: dict[str, Any]) -> dict[str, Any]:
    return row["episode_transition"]["state_t"]


def label(row: dict[str, Any]) -> str:
    return str(obs(row).get("boundary_next_token_match"))


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
    source_audit = load_json(SOURCE_AUDIT)
    rows = load_jsonl(MANIFEST)
    logits = load_jsonl(LOGITS)
    failures: list[str] = []
    if source.get("passed") is not False:
        failures.append("stage9647_was_not_quality_failure")
    if source_audit.get("safety_passed") is not True:
        failures.append("stage9647_safety_not_clean")
    if not rows or not logits:
        failures.append("missing_inputs")

    prefix_labels: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for row in rows:
        prefix = str(state(row).get("generation_prefix_text"))
        prefix_labels[prefix][str(row.get("split"))][label(row)] += 1
    prefix_conflict_examples = {
        prefix: {split: dict(counts) for split, counts in split_map.items()}
        for prefix, split_map in prefix_labels.items()
        if len({next(iter(counts)) for counts in split_map.values() if counts}) > 1
    }

    pred_pairs = Counter(f"{row.get('split')}::{row.get('field')}::{row.get('target')}=>{row.get('pred')}" for row in logits if row.get("correct") is False)
    pred_by_split = Counter(f"{row.get('split')}::{row.get('field')}::{row.get('pred')}" for row in logits)
    train_logits = [row for row in logits if row.get("split") == "train"]

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "prefix_conflict_examples": prefix_conflict_examples,
        "train_logits_rows": len(train_logits),
        "pred_by_split": dict(pred_by_split.most_common()),
        "wrong_pairs": dict(pred_pairs.most_common(20)),
        "module_delta_summary": "encoder and target structured heads changed; decoder delta remained zero",
        "diagnosis": (
            "Stage9647 did not prove the comparison operation. The manifest reused prefixes with opposite labels "
            "across splits, so the model could key on prefix identity instead of boundary_expected_token_text versus "
            "boundary_generated_token_text. Train logits were not emitted, so the recorded train exact proxy is not "
            "strong evidence. The next manifest must include same-prefix positive/negative pairs within every split."
        ),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9649 same-prefix boundary/prefix contrast manifest with positive and negative pairs for each prefix inside train/eval/strict."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Stage9647 failed safely; patch the manifest to same-prefix contrast before another micro probe.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9648 Micro-Overfit Failure Audit", "", f"Passed: `{audit['passed']}`", f"Train logits rows: `{len(train_logits)}`", f"Prefix conflicts: `{prefix_conflict_examples}`", f"Top wrong pairs: `{dict(pred_pairs.most_common(10))}`", "", audit["diagnosis"], "", "Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
