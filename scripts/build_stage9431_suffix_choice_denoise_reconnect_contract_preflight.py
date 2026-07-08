#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9431
NAME = "stage9431_suffix_choice_denoise_reconnect_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9430_suffix_choice_denoise_reconnect_wrapper_audit.json"
PROBE_DIR = ROOT / "runs/local/probes/stage9429_suffix_choice_denoise_reconnect_contract_only"
CONTRACT_AUDIT = PROBE_DIR / "probe_contract_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREFLIGHT = OUT_DIR / "suffix_choice_denoise_reconnect_contract_preflight.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_DENOISE_RECONNECT_CONTRACT_PREFLIGHT_STAGE9431.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    audit = load_json(CONTRACT_AUDIT)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9430_not_passed")
    if audit.get("passed") is not True:
        failures.append("trainer_contract_audit_not_passed")
    if audit.get("model_execution_attempted"):
        failures.append("model_execution_attempted")
    if audit.get("unsafe_loss_rows") != 0:
        failures.append("unsafe_loss_rows_present")
    if audit.get("authority_rows") != 0:
        failures.append("authority_rows_present")
    weights = audit.get("weights") or {}
    for key in ("decoder_ce_weight", "structured_aux_weight", "denoise_weight"):
        if float(weights.get(key, 1.0)) != 0.0:
            failures.append(f"{key}_not_zero")
    caps = audit.get("caps") or {}
    if int(caps.get("max_steps", -1)) != 0:
        failures.append("max_steps_not_zero")
    split_counts = audit.get("split_counts") or {}
    if split_counts.get("eval") != 5 or split_counts.get("strict_eval") != 4:
        failures.append("unexpected_split_counts")
    if audit.get("rows") != 9:
        failures.append("unexpected_row_count")

    preflight = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9430_suffix_choice_denoise_reconnect_wrapper_audit",
        "trainer_contract_audit": str(CONTRACT_AUDIT.relative_to(ROOT)),
        "probe_dir": str(PROBE_DIR.relative_to(ROOT)),
        "rows": audit.get("rows"),
        "split_counts": split_counts,
        "unsafe_loss_rows": audit.get("unsafe_loss_rows"),
        "authority_rows": audit.get("authority_rows"),
        "model_execution_attempted": audit.get("model_execution_attempted"),
        "weights": weights,
        "caps": caps,
        "manifest_sha256": audit.get("manifest_sha256"),
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "contract-only preflight passed; execution and denoise training remain closed",
    }
    PREFLIGHT.write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": preflight["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "rows": audit.get("rows"),
            "eval_rows": split_counts.get("eval"),
            "strict_eval_rows": split_counts.get("strict_eval"),
            "unsafe_loss_rows": audit.get("unsafe_loss_rows"),
            "authority_rows": audit.get("authority_rows"),
            "model_execution_attempted": audit.get("model_execution_attempted"),
            "max_steps": caps.get("max_steps"),
            "decoder_ce_weight": weights.get("decoder_ce_weight"),
            "structured_aux_weight": weights.get("structured_aux_weight"),
            "denoise_weight": weights.get("denoise_weight"),
        },
        "artifacts": {
            "preflight": str(PREFLIGHT.relative_to(ROOT)),
            "trainer_contract_audit": str(CONTRACT_AUDIT.relative_to(ROOT)),
            "probe_dir": str(PROBE_DIR.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": (
            "Captured the suffix-choice denoise reconnect contract-only preflight. It passed without model "
            "execution, without unsafe loss rows, and with decoder/structured/denoise weights all zero."
        ),
        "next_best_step": (
            "Write a separate execution-authorization review before any nonzero denoise reconnect probe; the "
            "review must keep quarantined suffix-choice residual rows excluded."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9431 Suffix Choice Denoise Reconnect Contract Preflight",
                "",
                f"Passed: `{preflight['passed']}`",
                f"Rows: `{audit.get('rows')}`",
                f"Unsafe loss rows: `{audit.get('unsafe_loss_rows')}`",
                f"Model execution attempted: `{audit.get('model_execution_attempted')}`",
                f"Max steps: `{caps.get('max_steps')}`",
                f"Denoise weight: `{weights.get('denoise_weight')}`",
                "",
                "This stage validates the wrapper contract only. It does not authorize denoise execution or training.",
                "",
            ]
        )
    )

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
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
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": {
                    "rows": audit.get("rows"),
                    "unsafe_loss_rows": audit.get("unsafe_loss_rows"),
                    "model_execution_attempted": audit.get("model_execution_attempted"),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
