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
STAGE = 9588
NAME = "stage9588_residual_denoise_counterbalanced_sidecar_shortcut_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9587_residual_denoise_counterbalanced_sidecar_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9587_residual_denoise_counterbalanced_sidecar_manifest/residual_denoise_counterbalanced_sidecar_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_counterbalanced_sidecar_shortcut_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_COUNTERBALANCED_SIDECAR_SHORTCUT_AUDIT_STAGE9588.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FORBIDDEN_FEATURES = [
    "language_family",
    "split",
    "objective_family",
    "route",
    "model_input.context_kept_language_family",
    "model_input.context_kept_action_type",
    "model_input.context_kept_bridge_error_family",
    "model_input.context_kept_prefix_token_bucket",
]
INTENDED_FEATURES = [
    "model_input.sidecar_boundary_next_token_miss_observed",
    "model_input.sidecar_prefix_only_observed",
    "model_input.obs_has_boundary_next_token_miss_reason",
    "model_input.obs_boundary_relation",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def target(row: dict[str, Any]) -> str:
    return str((row.get("target") or {}).get("suffix_choice") or "")


def nested(row: dict[str, Any], path: str) -> str:
    value: Any = row
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return "<missing>"
    return "<missing>" if value is None else str(value)


def baseline_exact(rows: list[dict[str, Any]], features: list[str]) -> dict[str, Any]:
    groups: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        groups[tuple(nested(row, f) for f in features)][target(row)] += 1
    correct = sum(max(counter.values()) for counter in groups.values())
    return {
        "features": features,
        "exact": correct / len(rows) if rows else None,
        "groups": len(groups),
        "largest_group": max((sum(counter.values()) for counter in groups.values()), default=0),
    }


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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9587_not_passed")
    if len(rows) != 96:
        failures.append("manifest_row_count_not_96")
    counts = Counter(target(row) for row in rows)
    majority = max(counts.values()) / len(rows) if rows else None
    forbidden = [baseline_exact(rows, [feature]) for feature in FORBIDDEN_FEATURES]
    forbidden_pairs = [baseline_exact(rows, [a, b]) for i, a in enumerate(FORBIDDEN_FEATURES) for b in FORBIDDEN_FEATURES[i+1:]]
    intended = [baseline_exact(rows, [feature]) for feature in INTENDED_FEATURES]
    strongest_forbidden = max((item["exact"] for item in forbidden + forbidden_pairs if item["exact"] is not None), default=None)
    strongest_intended = max((item["exact"] for item in intended if item["exact"] is not None), default=None)
    if majority != 0.5:
        failures.append("majority_not_half")
    if strongest_forbidden is None or strongest_forbidden > 0.55:
        failures.append("forbidden_shortcut_above_ceiling")
    if strongest_intended != 1.0:
        failures.append("intended_verifier_feature_not_predictive")
    if any(any((row.get("authority") or {}).values()) for row in rows):
        failures.append("authority_rows_present")
    if any((row.get("target") or {}).get("decoder_text") or row.get("decoder_text") for row in rows):
        failures.append("decoder_text_rows_present")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "target_counts": dict(sorted(counts.items())),
        "majority_exact": majority,
        "forbidden_single_feature_baselines": forbidden,
        "forbidden_pair_feature_baselines": forbidden_pairs,
        "intended_verifier_feature_baselines": intended,
        "strongest_forbidden_exact": strongest_forbidden,
        "strongest_intended_exact": strongest_intended,
        "training_blocked_by_shortcut_dominance": bool(failures),
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited the counterbalanced sidecar manifest. Non-verifier shortcuts must stay at majority while verifier evidence remains the intended discriminator.",
        "next_best_step": "Run the capped suffix_choice sidecar probe over the counterbalanced manifest if the shortcut audit passed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9588 Residual Denoise Counterbalanced Sidecar Shortcut Audit", "", f"Passed: `{audit['passed']}`", f"Majority exact: `{majority}`", f"Strongest forbidden exact: `{strongest_forbidden}`", f"Strongest intended exact: `{strongest_intended}`", "", "The verifier evidence feature is allowed to solve the task; non-verifier shortcuts are not.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "majority_exact": majority, "strongest_forbidden_exact": strongest_forbidden, "strongest_intended_exact": strongest_intended, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
