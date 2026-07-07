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
STAGE = 9208
NAME = "stage9208_repo_local_execution_review_matrix"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9207 = ROOT / "runs/summaries/stage9207_three_family_contract_only_handoff.json"
SELECTED_BUNDLES = ROOT / "runs/local/artifacts/stage9206_repo_local_three_family_selector/selected_repo_local_three_family_bundles.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_EXECUTION_REVIEW_MATRIX_STAGE9208.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "repo_local_execution_review_matrix.json"

AUTHORIZATION_SOURCES = {
    "structured_policy_probe": ROOT / "runs/summaries/stage8882_tiny_structured_probe_execution_authorization_review.json",
    "bounded_decoder_ce_probe": ROOT / "runs/summaries/stage8956_bounded_decoder_future_one_run_authorization_schema.json",
    "denoise_repair_probe": ROOT / "runs/summaries/stage8884_no_execution_denoise_authorization_review.json",
    "trainer_execution_review": ROOT / "runs/summaries/stage9104_trainer_execution_authorization_review_refresh.json",
}

STRUCTURED_TINY_LIMITS = {
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 8,
}

BOUNDED_DECODER_TINY_LIMITS = {
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 16,
}

DEFAULT_TINY_LIMITS = {
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 8,
}

LOSS_EXPECTATIONS = {
    "structured_policy_probe": {
        "decoder-ce-weight": "0.0",
        "structured-aux-weight": "1.0",
        "denoise-weight": "0.0",
    },
    "bounded_decoder_ce_probe": {
        "decoder-ce-weight": "1.0",
        "structured-aux-weight": "0.0",
        "denoise-weight": "0.0",
    },
    "denoise_repair_probe": {
        "decoder-ce-weight": "0.0",
        "structured-aux-weight": "0.0",
        "denoise-weight": "1.0",
    },
}

DENIED_NOW_OPERATIONS = [
    "run_trainer",
    "instantiate_model",
    "run_model_forward",
    "run_backward",
    "create_optimizer",
    "write_checkpoint",
    "export_checkpoint",
    "run_runtime",
    "call_gemma",
    "score_output",
    "emit_source_body",
    "walk_arxiv",
    "mine_repositories",
    "cleanup_checkpoints",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def command_value(command: list[str], flag: str) -> str | None:
    needle = f"--{flag}"
    for idx, token in enumerate(command):
        if token == needle and idx + 1 < len(command):
            return str(command[idx + 1])
    return None


def command_has_flag(command: list[str], flag: str) -> bool:
    return f"--{flag}" in command


def command_int(command: list[str], flag: str) -> int | None:
    value = command_value(command, flag)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def command_limits(command: list[str]) -> dict[str, int | None]:
    return {
        "max_train_rows": command_int(command, "max-train-rows"),
        "max_eval_rows": command_int(command, "max-eval-rows"),
        "max_strict_rows": command_int(command, "max-strict-rows"),
        "max_steps": command_int(command, "max-steps"),
    }


def limit_failures(command: list[str], limits: dict[str, int]) -> list[str]:
    failures: list[str] = []
    observed = command_limits(command)
    for key, cap in limits.items():
        value = observed.get(key)
        if value is None:
            failures.append(f"missing:{key}")
        elif value > cap:
            failures.append(f"{key}:{value}>{cap}")
    return failures


def loss_failures(command: list[str], mode: str) -> list[str]:
    expected = LOSS_EXPECTATIONS.get(mode, {})
    failures: list[str] = []
    for flag, value in expected.items():
        observed = command_value(command, flag)
        if observed != value:
            failures.append(f"{flag}:{observed}!={value}")
    return failures


def required_flag_failures(command: list[str]) -> list[str]:
    required = [
        "manifest",
        "mode",
        "output-dir",
        "require-loss-mask-enforcement-audit",
        "no-final-checkpoint-export",
    ]
    failures: list[str] = []
    for flag in required:
        if flag in {"require-loss-mask-enforcement-audit", "no-final-checkpoint-export"}:
            if not command_has_flag(command, flag):
                failures.append(f"missing_flag:{flag}")
        elif command_value(command, flag) is None:
            failures.append(f"missing_value:{flag}")
    if command_has_flag(command, "cleanup-checkpoints-after-probe"):
        failures.append("cleanup_flag_present_before_explicit_execution")
    return failures


def tiny_limits_for_mode(mode: str) -> dict[str, int]:
    if mode == "structured_policy_probe":
        return dict(STRUCTURED_TINY_LIMITS)
    if mode == "bounded_decoder_ce_probe":
        return dict(BOUNDED_DECODER_TINY_LIMITS)
    return dict(DEFAULT_TINY_LIMITS)


def review_bundle(bundle: dict[str, Any], auth_sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    mode = str(bundle.get("preferred_mode") or "")
    preview = bundle.get("bundle_preview") or {}
    trainer_input = preview.get("trainer_input") or {}
    commands = trainer_input.get("recommended_commands") or []
    command_spec = next((item for item in commands if item.get("mode") == mode), {})
    command = list(command_spec.get("command") or [])
    limits = tiny_limits_for_mode(mode)
    failures = []
    if not preview.get("materialization_passed"):
        failures.append("materialization_not_passed")
    if mode not in (preview.get("eligible_modes") or []):
        failures.append("preferred_mode_not_eligible")
    failures.extend(limit_failures(command, limits))
    failures.extend(loss_failures(command, mode))
    failures.extend(required_flag_failures(command))
    if any((trainer_input.get("authority") or {}).values()):
        failures.append("trainer_input_authority_open")
    if not auth_sources.get(mode, {}).get("passed"):
        failures.append(f"authorization_source_not_passed:{mode}")
    if not auth_sources.get("trainer_execution_review", {}).get("passed"):
        failures.append("trainer_execution_review_source_not_passed")

    status = "future_review_candidate"
    if mode == "bounded_decoder_ce_probe" and failures:
        status = "requires_tiny_cap_adapter_before_ticket"
    elif mode == "denoise_repair_probe" and failures:
        status = "requires_dedicated_one_run_schema_and_tiny_cap_adapter"
    elif failures:
        status = "blocked_until_review_failures_resolved"

    return {
        "bundle_id": bundle.get("bundle_id"),
        "mode": mode,
        "status": status,
        "review_failures": failures,
        "limits": {
            "observed": command_limits(command),
            "required_caps": limits,
        },
        "loss_weights": {
            "decoder_ce_weight": command_value(command, "decoder-ce-weight"),
            "structured_aux_weight": command_value(command, "structured-aux-weight"),
            "denoise_weight": command_value(command, "denoise-weight"),
        },
        "split_counts": trainer_input.get("split_counts") or {},
        "manifest_path": command_value(command, "manifest"),
        "output_dir": command_value(command, "output-dir"),
        "authorization_source_passed": bool(auth_sources.get(mode, {}).get("passed")),
        "same_stage_execution_authorized": False,
        "next_stage_execution_authorized": False,
    }


def build_matrix() -> dict[str, Any]:
    source_9207 = load_json(SOURCE_9207)
    selected = load_json_list(SELECTED_BUNDLES)
    auth_sources = {name: load_json(path) for name, path in AUTHORIZATION_SOURCES.items()}
    family_reviews = [review_bundle(bundle, auth_sources) for bundle in selected]
    review_ready = [
        item for item in family_reviews
        if not item["review_failures"] and item["mode"] == "structured_policy_probe"
    ]
    checks = {
        "source_stage9207_passed": source_9207.get("passed") is True,
        "selected_bundles_present": len(selected) >= 3,
        "three_family_reviews_written": len(family_reviews) >= 3,
        "authorization_sources_present": all(path.exists() for path in AUTHORIZATION_SOURCES.values()),
        "trainer_execution_review_passed": auth_sources.get("trainer_execution_review", {}).get("passed") is True,
        "at_least_one_future_review_candidate": len(review_ready) >= 1,
        "same_stage_execution_closed": True,
        "next_stage_execution_closed": True,
        "all_authority_closed": True,
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REPO_LOCAL_EXECUTION_REVIEW_MATRIX_NO_EXECUTION",
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
        "denied_operations_now": list(DENIED_NOW_OPERATIONS),
        "family_reviews": family_reviews,
        "recommended_first_future_ticket": (
            review_ready[0]["mode"] if review_ready else None
        ),
        "decision": (
            "Repo-local contract-only handoff is complete. The structured-policy bundle is the only current "
            "family close enough for a future explicit one-run ticket review. Bounded decoder and denoise remain "
            "blocked on tiny-cap/ticket-schema work. This stage authorizes no execution."
        ),
        "next_best_step": (
            "Build a structured-policy one-run ticket design from the repo-local Stage9206 manifest, or patch "
            "tiny-cap adapters for bounded decoder and denoise. Do not execute trainer from this review matrix."
        ),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row for row in registry.get("rows", [])
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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    matrix = build_matrix()
    MATRIX.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": matrix["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "family_reviews": len(matrix["family_reviews"]),
            "families_without_review_failures": sum(1 for item in matrix["family_reviews"] if not item["review_failures"]),
            "denied_operations_now": len(matrix["denied_operations_now"]),
            "same_stage_execution_authorized": False,
            "next_stage_execution_authorized": False,
            "model_execution_authorized": False,
            "runtime_authorized": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "backward_attempted": False,
            "optimizer_created": False,
            "cleanup_authorized_now": False,
            "recommended_first_future_ticket": matrix["recommended_first_future_ticket"],
            "failures": matrix["failures"],
        },
        "artifacts": {
            "matrix": str(MATRIX.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": matrix["decision"] if matrix["passed"] else "Repo-local execution review matrix failed.",
        "next_best_step": matrix["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9208 Repo-Local Execution Review Matrix",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage reviews the three real repo-local contract-only families after Stage9207.",
                "It does not invoke the trainer, load model weights, run forward/backward, write checkpoints, clean outputs, or touch /arxiv.",
                "",
                f"Family reviews: `{summary['metrics']['family_reviews']}`",
                f"Families without review failures: `{summary['metrics']['families_without_review_failures']}`",
                f"Recommended first future ticket: `{summary['metrics']['recommended_first_future_ticket']}`",
                "",
                "Current read:",
                "- `structured_policy_probe` is the closest future one-run candidate.",
                "- `bounded_decoder_ce_probe` still needs a tiny-cap adapter before any ticket.",
                "- `denoise_repair_probe` still needs a dedicated one-run schema and tiny-cap adapter.",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
