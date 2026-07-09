#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9654
NAME = "stage9654_episode_collator_visibility_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9653_comparator_feature_tiny_probe.json"
TRAINING_DATA = ROOT / "legacy_src/agentkernel_lite/training_data.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "episode_collator_visibility_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_COLLATOR_VISIBILITY_AUDIT_STAGE9654.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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
    text = TRAINING_DATA.read_text(encoding="utf-8")
    failures: list[str] = []
    if source.get("passed") is not False:
        failures.append("stage9653_was_not_quality_failure")
    encoder_text_consumed = "row.get(\"encoder_text\")" in text or "row.get('encoder_text')" in text
    state_features_consumed = "row.get(\"state_features\")" in text or "row.get('state_features')" in text
    model_input_consumed = "row.get(\"model_input\")" in text or "row.get('model_input')" in text
    input_state_consumed = "row.get(\"input_state\")" in text or "row.get('input_state')" in text
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "training_data_path": str(TRAINING_DATA.relative_to(ROOT)),
        "encoder_text_consumed_by_row_text": encoder_text_consumed,
        "state_features_consumed_by_row_text": state_features_consumed,
        "model_input_consumed_by_row_text": model_input_consumed,
        "input_state_consumed_by_row_text": input_state_consumed,
        "visible_episode_fields": ["episode_transition.state_t", "episode_transition.action_t", "model_input", "input_state", "query", "graph_input summaries"],
        "hidden_episode_fields": ["episode_transition.observation_t", "episode_transition.reward_or_verifier", "episode_transition.state_t_plus_1", "encoder_text", "state_features"],
        "diagnosis": "The recovered collator builds encoder input through _row_text and does not consume encoder_text or state_features. The boundary evidence added in Stages9646-9653 was therefore mostly invisible except for state_t/action metadata. Put comparator evidence in model_input or input_state for the next probe.",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9655 model_input comparator manifest so boundary_token_relation is visible to _row_text, then rerun the micro probe."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Stage9653 failed safely because comparator evidence was not in a collator-visible field.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9654 Episode Collator Visibility Audit", "", f"Passed: `{audit['passed']}`", f"`encoder_text` consumed: `{encoder_text_consumed}`", f"`state_features` consumed: `{state_features_consumed}`", f"`model_input` consumed: `{model_input_consumed}`", f"`input_state` consumed: `{input_state_consumed}`", "", audit["diagnosis"], "", "Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
