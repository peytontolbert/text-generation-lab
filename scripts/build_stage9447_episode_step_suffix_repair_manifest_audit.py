#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9447
NAME = "stage9447_episode_step_suffix_repair_manifest_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9446_episode_step_suffix_repair_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9446_episode_step_suffix_repair_manifest/episode_step_suffix_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "episode_step_suffix_repair_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_SUFFIX_REPAIR_MANIFEST_AUDIT_STAGE9447.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    split_counts = Counter()
    outcome_counts = Counter()
    phase_counts = Counter()
    authority_rows: list[str] = []
    open_loss_rows: list[str] = []
    target_label_leak_rows: list[str] = []
    copied_target_prefix_rows: list[str] = []
    missing_transition_rows: list[str] = []
    duplicate_ids = [row_id for row_id, count in Counter(str(row.get("row_id")) for row in rows).items() if count > 1]

    for row in rows:
        row_id = str(row.get("row_id"))
        transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
        state_t = transition.get("state_t") if isinstance(transition.get("state_t"), dict) else {}
        action_t = transition.get("action_t") if isinstance(transition.get("action_t"), dict) else {}
        state_next = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        target_choice = str(state_next.get("target_suffix_choice") or "")
        state_action_blob = json.dumps({"state_t": state_t, "action_t": action_t}, sort_keys=True)
        prefix = str(state_t.get("active_generation_prefix_span") or "")
        target_text = str(state_next.get("decoder_text") or "")
        split_counts[str(row.get("split"))] += 1
        outcome_counts[str(state_next.get("repair_outcome"))] += 1
        phase_counts[str(row.get("phase"))] += 1
        if any(bool(v) for v in authority.values()):
            authority_rows.append(row_id)
        if any(bool(loss_mask.get(key)) for key in ("decoder_ce", "denoise_ce", "runtime_reward", "episode_step_ce")):
            open_loss_rows.append(row_id)
        if target_choice and target_choice in state_action_blob:
            target_label_leak_rows.append(row_id)
        if prefix and target_text and prefix == target_text:
            copied_target_prefix_rows.append(row_id)
        if not transition or not state_t or not action_t or not state_next:
            missing_transition_rows.append(row_id)

    if source.get("passed") is not True:
        failures.append("source_stage9446_not_passed")
    if len(rows) != 50:
        failures.append("unexpected_row_count")
    if duplicate_ids:
        failures.append("duplicate_row_ids")
    if authority_rows:
        failures.append("authority_rows_present")
    if open_loss_rows:
        failures.append("loss_authority_opened")
    if target_label_leak_rows:
        failures.append("target_suffix_label_leak")
    if copied_target_prefix_rows:
        failures.append("target_copied_to_prefix")
    if missing_transition_rows:
        failures.append("missing_transition_fields")
    if phase_counts != Counter({"repair": 50}):
        failures.append("unexpected_phase_counts")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9446_episode_step_suffix_repair_manifest",
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "phase_counts": dict(sorted(phase_counts.items())),
        "duplicate_row_ids": duplicate_ids,
        "authority_rows": len(authority_rows),
        "authority_row_examples": authority_rows[:10],
        "open_loss_rows": len(open_loss_rows),
        "open_loss_row_examples": open_loss_rows[:10],
        "target_label_leak_rows": len(target_label_leak_rows),
        "target_label_leak_examples": target_label_leak_rows[:10],
        "copied_target_prefix_rows": len(copied_target_prefix_rows),
        "missing_transition_rows": len(missing_transition_rows),
        "schema": "episode_step_suffix_transition_v1",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited the episode-step suffix repair manifest; no training or execution authority opened.",
        "next_best_step": "If Stage9447 passes, design a no-execution wrapper for episode-step denoise supervision; decoder CE remains closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9447 Episode-Step Suffix Repair Manifest Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Target-label leak rows: `{len(target_label_leak_rows)}`",
        f"Open loss rows: `{len(open_loss_rows)}`",
        f"Authority rows: `{len(authority_rows)}`",
        "",
        "The manifest is only a contract/data-shape artifact. Decoder CE and denoise CE remain closed until a separate authorization stage.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "target_label_leak_rows": len(target_label_leak_rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
