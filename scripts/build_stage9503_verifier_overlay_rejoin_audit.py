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
STAGE = 9503
NAME = "stage9503_verifier_overlay_rejoin_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9502_verifier_overlay_rejoin_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9502_verifier_overlay_rejoin_manifest/verifier_overlay_rejoin_manifest.jsonl"
CARD = ROOT / "runs/local/artifacts/stage9502_verifier_overlay_rejoin_manifest/verifier_overlay_rejoin_manifest_card.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9503_verifier_overlay_rejoin_audit"
AUDIT = OUT_DIR / "verifier_overlay_rejoin_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIER_OVERLAY_REJOIN_AUDIT_STAGE9503.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

EFFECTIVE_KEYS = {
    "effective_boundary_match",
    "effective_target_prefix_match",
    "effective_failure_type",
    "effective_repair_outcome",
    "effective_step_value",
    "effective_step_passed",
}


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

    source_summary = load_json(SOURCE_SUMMARY)
    card = load_json(CARD)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("stage9502_summary_not_passed")
    if card.get("passed") is not True:
        failures.append("stage9502_card_not_passed")
    if len(rows) != 66:
        failures.append("unexpected_row_count")

    split_counts = Counter(row.get("split") for row in rows)
    enabled_losses = Counter()
    authority_rows: list[str] = []
    missing_effective_rows: list[str] = []
    effective_leak_rows: list[str] = []
    model_input_effective_keys = Counter()
    for row in rows:
        row_id = row.get("row_id")
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row_id)
        for loss_name, enabled in (row.get("loss_mask") or {}).items():
            if enabled:
                enabled_losses[loss_name] += 1
        effective = row.get("effective_verifier") if isinstance(row.get("effective_verifier"), dict) else {}
        if not EFFECTIVE_KEYS.issubset(effective):
            missing_effective_rows.append(row_id)
        elif any(effective.get(key) is None for key in EFFECTIVE_KEYS):
            missing_effective_rows.append(row_id)
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        leaked = sorted(key for key in model_input if key in EFFECTIVE_KEYS or key.startswith("effective_"))
        if leaked:
            effective_leak_rows.append(row_id)
            for key in leaked:
                model_input_effective_keys[key] += 1
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if missing_effective_rows:
        failures.append("missing_effective_verifier_rows")
    if effective_leak_rows:
        failures.append("effective_verifier_labels_in_model_input")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "enabled_losses": dict(sorted(enabled_losses.items())),
        "authority_rows": authority_rows,
        "missing_effective_rows": missing_effective_rows,
        "effective_leak_rows": effective_leak_rows,
        "model_input_effective_keys": dict(sorted(model_input_effective_keys.items())),
        "contract_checks": {
            "all_losses_closed": not enabled_losses,
            "effective_verifier_complete": not missing_effective_rows,
            "effective_verifier_outside_model_input": not effective_leak_rows,
            "authority_closed": not authority_rows,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
        },
        "decision": "Verifier overlay rejoin manifest is safe as control/evaluation metadata only. It is not a model-execution manifest because no losses are enabled.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "promotion_ready": False,
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
        "decision": audit["decision"],
        "next_best_step": "Return to trainable transition heads using verifier overlays as deterministic routing metadata; do not train verifier heads as authority.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    DOC.write_text("\n".join([
        "# Stage9503 Verifier Overlay Rejoin Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Enabled losses: `{dict(enabled_losses)}`",
        f"Authority rows: `{len(authority_rows)}`",
        f"Effective verifier leaks into model_input: `{len(effective_leak_rows)}`",
        "",
        audit["decision"],
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "rows": len(rows), "enabled_losses": dict(enabled_losses), "effective_leak_rows": len(effective_leak_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
