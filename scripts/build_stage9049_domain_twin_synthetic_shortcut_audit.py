#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9049
NAME = "stage9049_domain_twin_synthetic_shortcut_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9048 = ROOT / "runs/summaries/stage9048_domain_twin_synthetic_adapter_validator.json"
ROWS_9048 = ROOT / "runs/local/artifacts/stage9048_domain_twin_synthetic_adapter_validator/synthetic_domain_twin_adapter_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DOMAIN_TWIN_SYNTHETIC_SHORTCUT_AUDIT_STAGE9049.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "domain_twin_synthetic_shortcut_audit.json"

FEATURES_AUDITED = ["source_manifest_family", "source_ref_id", "semantic_key", "split", "adapter_status"]
TARGETS_AUDITED = ["route", "any_loss_enabled", "all_gate_status_passed"]
FORBIDDEN_NOW = [
    "treat_synthetic_shortcut_result_as_training_quality",
    "train_on_synthetic_adapter_rows",
    "materialize_real_rows",
    "scan_arxiv",
    "scan_repository_library",
    "run_model",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def exact_baseline(rows: list[dict[str, Any]], feature: str, target: str) -> float:
    if not rows:
        return 0.0
    grouped: dict[str, Counter[str]] = {}
    for row in rows:
        x = json.dumps(row.get(feature), sort_keys=True)
        if target == "any_loss_enabled":
            y = str(any((row.get("loss_mask") or {}).values()))
        elif target == "all_gate_status_passed":
            y = str(all((row.get("gate_status") or {}).values()))
        else:
            y = str(row.get(target))
        grouped.setdefault(x, Counter())[y] += 1
    correct = 0
    for row in rows:
        x = json.dumps(row.get(feature), sort_keys=True)
        pred, _ = grouped[x].most_common(1)[0]
        if target == "any_loss_enabled":
            actual = str(any((row.get("loss_mask") or {}).values()))
        elif target == "all_gate_status_passed":
            actual = str(all((row.get("gate_status") or {}).values()))
        else:
            actual = str(row.get(target))
        correct += int(pred == actual)
    return correct / len(rows)


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9048 = load_json(SOURCE_9048)
    rows = read_jsonl(ROWS_9048) if ROWS_9048.exists() else []
    baselines = {
        f"{feature}->{target}": exact_baseline(rows, feature, target)
        for feature in FEATURES_AUDITED
        for target in TARGETS_AUDITED
    }
    checks = {
        "source_stage9048_present": SOURCE_9048.exists(),
        "source_stage9048_passed": s9048.get("passed") is True,
        "synthetic_rows_present": len(rows) == 4,
        "all_rows_route_needs_human_review": all(row.get("route") == "NEEDS_HUMAN_REVIEW" for row in rows),
        "all_loss_masks_closed": all(not any((row.get("loss_mask") or {}).values()) for row in rows),
        "all_gate_status_not_passed": all(not all((row.get("gate_status") or {}).values()) for row in rows),
        "shortcut_baselines_recorded": len(baselines) == len(FEATURES_AUDITED) * len(TARGETS_AUDITED),
        "audit_interpreted_as_nontraining_only": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "DOMAIN_TWIN_SYNTHETIC_SHORTCUT_AUDIT_NO_TRAINING",
        "features_audited": FEATURES_AUDITED,
        "targets_audited": TARGETS_AUDITED,
        "baselines": baselines,
        "forbidden_now": FORBIDDEN_NOW,
        "checks": checks,
        "metrics": {
            "synthetic_rows": len(rows),
            "baseline_count": len(baselines),
            "max_baseline_exact": max(baselines.values()) if baselines else 0.0,
            "shortcut_audit_only": True,
            "training_quality_claim_allowed": False,
            "synthetic_rows_trainable": False,
            "real_rows_materialized_now": False,
            "arxiv_scan_authorized_now": False,
            "repository_library_scan_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Synthetic adapter rows are intentionally shortcut-solvable because every row is blocked; this audit proves they are nontraining fixtures only, not model-quality evidence.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "training_quality_claim_allowed",
        "synthetic_rows_trainable",
        "real_rows_materialized_now",
        "arxiv_scan_authorized_now",
        "repository_library_scan_authorized_now",
        "training_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
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
        "artifacts": {"shortcut_audit": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Return to real-readiness blockers: active source tickets, operator-detail metadata patch validation, or a fixture-only Domain/Twin adapter compiler smoke. Do not train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9049 Domain/Twin Synthetic Shortcut Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This audit checks the synthetic adapter rows only. They are intentionally all blocked and nontrainable, so shortcut-solvability is not a model-training signal.",
        "",
        f"Synthetic rows: `{summary['metrics']['synthetic_rows']}`",
        f"Max baseline exact: `{summary['metrics']['max_baseline_exact']}`",
        f"Synthetic rows trainable: `{summary['metrics']['synthetic_rows_trainable']}`",
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
