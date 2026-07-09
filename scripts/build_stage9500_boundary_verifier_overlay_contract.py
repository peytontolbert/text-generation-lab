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
STAGE = 9500
NAME = "stage9500_boundary_verifier_overlay_contract"
MANIFEST = ROOT / "runs/local/artifacts/stage9497_boundary_negative_counterbalance_manifest/boundary_negative_counterbalance_manifest.jsonl"
STAGE9496 = ROOT / "runs/summaries/stage9496_boundary_verifier_probe_audit.json"
STAGE9499 = ROOT / "runs/summaries/stage9499_boundary_counterbalance_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9500_boundary_verifier_overlay_contract"
CONTRACT = OUT_DIR / "boundary_verifier_overlay_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDARY_VERIFIER_OVERLAY_CONTRACT_STAGE9500.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def boundary_label(row: dict) -> bool | None:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
    value = observation.get("boundary_next_token_match")
    return value if isinstance(value, bool) else None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(MANIFEST)
    stage9496 = load_json(STAGE9496)
    stage9499 = load_json(STAGE9499)
    failures: list[str] = []
    if not rows:
        failures.append("missing_stage9497_manifest_rows")
    if stage9499.get("passed") is not False:
        failures.append("stage9499_not_recorded_as_safe_quality_failure")

    labels = {row.get("row_id"): boundary_label(row) for row in rows}
    missing_label_rows = sorted(row_id for row_id, label in labels.items() if label is None)
    if missing_label_rows:
        failures.append("missing_deterministic_boundary_labels")

    # The effective overlay is intentionally non-learned:
    # effective_boundary_match := observation_t.boundary_next_token_match.
    effective_wrong_rows = []
    false_boundary_accept_rows = []
    for row in rows:
        row_id = row.get("row_id")
        label = labels.get(row_id)
        effective = label
        if effective != label:
            effective_wrong_rows.append(row_id)
        if effective is True and label is False:
            false_boundary_accept_rows.append(row_id)
    if effective_wrong_rows:
        failures.append("effective_boundary_not_exact")
    if false_boundary_accept_rows:
        failures.append("effective_false_boundary_accepts")

    loss_masks = Counter()
    for row in rows:
        for key, enabled in (row.get("loss_mask") or {}).items():
            if enabled:
                loss_masks[key] += 1
    if dict(loss_masks) != {"episode_boundary_match_ce": len(rows)}:
        failures.append("unexpected_loss_mask_surface")

    authority_rows = [row.get("row_id") for row in rows if any((row.get("authority") or {}).values())]
    if authority_rows:
        failures.append("authority_rows_present")

    stage9496_metrics = stage9496.get("metrics", {}) if isinstance(stage9496.get("metrics"), dict) else {}
    stage9499_metrics = stage9499.get("metrics", {}) if isinstance(stage9499.get("metrics"), dict) else {}
    learned_stage9496 = {
        "final_eval_joint_proxy_exact": stage9496_metrics.get("final_eval_joint_proxy_exact"),
        "final_strict_joint_proxy_exact": stage9496_metrics.get("final_strict_joint_proxy_exact"),
        "wrong_rows": len(stage9496_metrics.get("wrong_rows") or []),
        "high_confidence_wrong_rows": len(stage9496_metrics.get("high_confidence_wrong_rows") or []),
    }
    learned_stage9499 = {
        "final_eval_joint_proxy_exact": stage9499_metrics.get("final_eval_joint_proxy_exact"),
        "final_strict_joint_proxy_exact": stage9499_metrics.get("final_strict_joint_proxy_exact"),
        "wrong_rows": len(stage9499_metrics.get("wrong_rows") or []),
        "high_confidence_wrong_rows": len(stage9499_metrics.get("high_confidence_wrong_rows") or []),
    }

    label_counts = Counter(str(label).lower() for label in labels.values())
    split_label_counts = Counter(f"{row.get('split')}::{str(labels.get(row.get('row_id'))).lower()}" for row in rows)
    contract = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(MANIFEST.relative_to(ROOT)),
        "source_probe_audits": {
            "stage9496": str(STAGE9496.relative_to(ROOT)),
            "stage9499": str(STAGE9499.relative_to(ROOT)),
        },
        "rows": len(rows),
        "label_counts": dict(sorted(label_counts.items())),
        "split_label_counts": dict(sorted(split_label_counts.items())),
        "effective_boundary_rule": "effective_boundary_match = observation_t.boundary_next_token_match",
        "learned_boundary_head_authority": "telemetry_only",
        "effective_boundary_exact": 1.0 if rows and not effective_wrong_rows and not missing_label_rows else 0.0,
        "effective_false_boundary_accept_rows": false_boundary_accept_rows,
        "missing_label_rows": missing_label_rows,
        "loss_masks_enabled": dict(sorted(loss_masks.items())),
        "authority_rows": authority_rows,
        "learned_head_stage9496": learned_stage9496,
        "learned_head_stage9499": learned_stage9499,
        "decision": "Do not let the learned boundary head authorize verifier acceptance. Boundary match is a deterministic verifier primitive; trainable predictions may remain telemetry until richer comparison objectives show robust heldout learning.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "promotion_ready": False,
    }
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": contract["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **contract},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": contract["decision"],
        "next_best_step": "Apply the same derived-vs-learned authority audit to failure_type, repair_outcome, step_value, and target_prefix before rejoining verifier heads.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    DOC.write_text("\n".join([
        "# Stage9500 Boundary Verifier Overlay Contract",
        "",
        f"Passed: `{contract['passed']}`",
        f"Rows: `{contract['rows']}`",
        f"Effective boundary exact: `{contract['effective_boundary_exact']}`",
        f"Effective false boundary accepts: `{len(false_boundary_accept_rows)}`",
        f"Stage9496 learned wrong rows: `{learned_stage9496['wrong_rows']}`",
        f"Stage9496 high-confidence wrong rows: `{learned_stage9496['high_confidence_wrong_rows']}`",
        f"Stage9499 learned wrong rows: `{learned_stage9499['wrong_rows']}`",
        f"Stage9499 high-confidence wrong rows: `{learned_stage9499['high_confidence_wrong_rows']}`",
        "",
        "## Contract",
        "",
        "`episode_boundary_match` is a deterministic verifier primitive for effective acceptance:",
        "",
        "`effective_boundary_match = observation_t.boundary_next_token_match`",
        "",
        "The learned boundary head remains telemetry-only. It must not authorize boundary acceptance or decoder promotion.",
        "",
        "## Rationale",
        "",
        "Stage9496 learned a true-majority shortcut with high-confidence false-boundary accepts. Stage9499 removed that collapse through counterbalancing, but the target-100M head fell to chance with low margins. This makes the label useful as a verifier fact, not as model authority.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"stage": STAGE, "passed": contract["passed"], "rows": len(rows), "effective_boundary_exact": contract["effective_boundary_exact"], "effective_false_boundary_accept_rows": len(false_boundary_accept_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
