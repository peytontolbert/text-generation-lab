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
STAGE = 9263
NAME = "stage9263_stabilized_bounded_decoder_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9262_bounded_decoder_stabilization_trainer_patch_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9263_stabilized_bounded_decoder_contract_only_preflight/bounded_decoder_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "stabilized_bounded_decoder_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STABILIZED_BOUNDED_DECODER_CONTRACT_PREFLIGHT_STAGE9263.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def audit_preflight() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    cleanup = load_json(RUN_DIR / "cleanup_proof.json")
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9262_not_passed")
    if card.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    if card.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted")
    if card.get("manifest_sha256") != "e9cf97f57f92b710e01b72350178c557a5ca7e05dbb44c7a29a8a7aedce8d06b":
        failures.append("manifest_hash_mismatch")
    if (card.get("weights") or {}).get("eos_loss_weight") != 4.0:
        failures.append("eos_loss_weight_not_4")
    if (card.get("weights") or {}).get("decoder_ce_weight") != 1.0:
        failures.append("decoder_ce_weight_not_1")
    if (card.get("weights") or {}).get("structured_aux_weight") != 0.0 or (card.get("weights") or {}).get("denoise_weight") != 0.0:
        failures.append("non_decoder_weights_enabled")
    if card.get("unsafe_loss_rows") != 0 or card.get("over_cap_rows") != 0 or card.get("empty_target_rows") != 0 or card.get("authority_rows") != 0:
        failures.append("row_contract_violation")
    if card.get("probe_scale") != "target_100m":
        failures.append("probe_scale_not_target_100m")
    if cleanup.get("cleanup_executed") is not False:
        failures.append("contract_cleanup_should_not_execute")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "rows": card.get("rows"),
            "train_rows": (card.get("split_counts") or {}).get("train"),
            "eval_rows": (card.get("split_counts") or {}).get("eval"),
            "strict_rows": (card.get("split_counts") or {}).get("strict_eval"),
            "decoder_ce_rows": (card.get("loss_counts") or {}).get("decoder_ce"),
            "eos_loss_weight": (card.get("weights") or {}).get("eos_loss_weight"),
            "decoder_ce_weight": (card.get("weights") or {}).get("decoder_ce_weight"),
            "model_execution_attempted": card.get("model_execution_attempted"),
            "generation_audit_requested": card.get("generation_audit_requested"),
            "probe_scale": card.get("probe_scale"),
            "manifest_sha256": card.get("manifest_sha256"),
            "authority_rows": card.get("authority_rows"),
            "unsafe_loss_rows": card.get("unsafe_loss_rows"),
            "over_cap_rows": card.get("over_cap_rows"),
            "empty_target_rows": card.get("empty_target_rows"),
            "second_execution_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_preflight()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "The stabilized target-100M bounded decoder contract-only preflight passed. No model execution occurred; a fresh execution review is still required before a second run.",
        "next_best_step": "Build Stage9264 stabilized bounded decoder execution review for one tiny target-100M rerun with --eos-loss-weight 4.0 and LR 1e-5.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9263 Stabilized Bounded Decoder Contract Preflight",
                "",
                "The second-run contract-only preflight passed after the Stage9262 trainer stabilization patch.",
                "",
                f"Rows: {audit['metrics']['rows']}",
                f"Decoder CE rows: {audit['metrics']['decoder_ce_rows']}",
                f"EOS loss weight: {audit['metrics']['eos_loss_weight']}",
                f"Probe scale: {audit['metrics']['probe_scale']}",
                f"Model execution attempted: {audit['metrics']['model_execution_attempted']}",
                "",
                "Execution is still not opened by this stage. A fresh execution review is required.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
