#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.curriculum_compiler import compile_rows
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from curriculum_compiler import compile_rows  # type: ignore
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9022
NAME = "stage9022_current_frontier_compiler_invocation_policy_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9021_SUMMARY = ROOT / "runs/summaries/stage9021_locked_manifest_compile_blocker_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_COMPILER_INVOCATION_POLICY_AUDIT_STAGE9022.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "current_frontier_compiler_invocation_policy_audit.json"

ALLOWED_CURRENT_FRONTIER_FLAGS = [
    "--input",
    "--output-dir",
    "--require-recovered-gates",
]

FORBIDDEN_CURRENT_FRONTIER_FLAGS = [
    "--allow-decoder",
    "--allow-denoise",
    "--allow-runtime",
]

SYNTHETIC_ROWS = [
    {"row_id": "synthetic_structured", "split": "train", "route": "KEEP_STRUCTURED"},
    {"row_id": "synthetic_decoder", "split": "eval", "route": "KEEP_BOUNDED_DECODER"},
    {"row_id": "synthetic_denoise", "split": "strict_eval", "route": "USE_FOR_DENOISE_REPAIR"},
    {"row_id": "synthetic_holdout", "split": "strict_eval", "route": "HOLD_LONG_OUTPUT"},
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def command_flags_allowed(flags: list[str]) -> tuple[bool, list[str]]:
    forbidden = [flag for flag in flags if flag in FORBIDDEN_CURRENT_FRONTIER_FLAGS]
    return not forbidden, forbidden


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    s9021 = load_json(SOURCE_9021_SUMMARY)
    buckets, card = compile_rows(
        SYNTHETIC_ROWS,
        allow_decoder=False,
        allow_denoise=False,
        allow_runtime=False,
        require_recovered_gates=False,
    )
    unsafe_ok, unsafe_forbidden = command_flags_allowed(["--input", "--output-dir", "--allow-decoder"])
    safe_ok, safe_forbidden = command_flags_allowed(["--input", "--output-dir", "--require-recovered-gates"])
    checks = {
        "source_stage9021_present": SOURCE_9021_SUMMARY.exists(),
        "source_stage9021_passed": s9021.get("passed") is True,
        "source_stage9021_blocks_manifest_compile": (s9021.get("metrics") or {}).get("manifest_compile_authorized_now") is False,
        "allowed_flags_recorded": len(ALLOWED_CURRENT_FRONTIER_FLAGS) == 3,
        "forbidden_flags_recorded": len(FORBIDDEN_CURRENT_FRONTIER_FLAGS) == 3,
        "safe_command_flags_accepted": safe_ok and not safe_forbidden,
        "unsafe_command_flags_rejected": unsafe_ok is False and unsafe_forbidden == ["--allow-decoder"],
        "synthetic_decoder_loss_blocked": card["loss_counts"].get("decoder_ce", 0) == 0,
        "synthetic_denoise_loss_blocked": card["loss_counts"].get("denoise_ce", 0) == 0,
        "synthetic_runtime_loss_blocked": card["loss_counts"].get("runtime_reward", 0) == 0,
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_COMPILER_INVOCATION_POLICY_AUDIT_NO_DATA",
        "allowed_current_frontier_flags": ALLOWED_CURRENT_FRONTIER_FLAGS,
        "forbidden_current_frontier_flags": FORBIDDEN_CURRENT_FRONTIER_FLAGS,
        "synthetic_compile_card": card,
        "synthetic_objective_counts": {key: len(value) for key, value in buckets.items()},
        "safe_command_policy": {"allowed": safe_ok, "forbidden_flags": safe_forbidden},
        "unsafe_command_policy": {"allowed": unsafe_ok, "forbidden_flags": unsafe_forbidden},
        "checks": checks,
        "metrics": {
            "synthetic_rows": len(SYNTHETIC_ROWS),
            "allowed_current_frontier_flags": len(ALLOWED_CURRENT_FRONTIER_FLAGS),
            "forbidden_current_frontier_flags": len(FORBIDDEN_CURRENT_FRONTIER_FLAGS),
            "decoder_loss_rows_under_current_policy": card["loss_counts"].get("decoder_ce", 0),
            "denoise_loss_rows_under_current_policy": card["loss_counts"].get("denoise_ce", 0),
            "runtime_loss_rows_under_current_policy": card["loss_counts"].get("runtime_reward", 0),
            "unsafe_compiler_flags_rejected": unsafe_ok is False,
            "manifest_compile_authorized_now": False,
            "manifest_materialized_now": False,
            "dataset_files_opened": False,
            "dataset_rows_loaded": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "trainer_dry_run_execution_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Under the current frontier, curriculum compiler invocation may only run no-data/synthetic or future judged metadata paths without decoder, denoise, or runtime flags.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "manifest_compile_authorized_now",
        "manifest_materialized_now",
        "dataset_files_opened",
        "dataset_rows_loaded",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "trainer_dry_run_execution_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
        "arxiv_write_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("decoder_loss_rows_under_current_policy") != 0:
        failures.append("decoder_loss_rows_under_current_policy")
    if card["metrics"].get("denoise_loss_rows_under_current_policy") != 0:
        failures.append("denoise_loss_rows_under_current_policy")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_audit(registry)
    failures = validate_audit(card)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Keep compiler invocations no-data/no-loss until real judged row IDs and gate status exist. Then design a separate locked manifest compile ticket.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9022 Current Frontier Compiler Invocation Policy Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This no-data audit records the current compiler invocation policy. Decoder, denoise, and runtime flags are forbidden at this frontier because manifest compilation remains blocked.",
                "",
                f"Decoder loss rows under current policy: `{summary['metrics']['decoder_loss_rows_under_current_policy']}`",
                f"Denoise loss rows under current policy: `{summary['metrics']['denoise_loss_rows_under_current_policy']}`",
                f"Unsafe compiler flags rejected: `{summary['metrics']['unsafe_compiler_flags_rejected']}`",
                f"Training authorized: `{summary['metrics']['training_authorized']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
