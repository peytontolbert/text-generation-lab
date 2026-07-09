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
STAGE = 9691
NAME = "stage9691_observe_repair_renderer_reconnect_decision"
SOURCES = {
    "observe_repair_promotion": ROOT / "runs/summaries/stage9665_observe_repair_control_promotion_contract.json",
    "guarded_observe_repair_contract": ROOT / "runs/summaries/stage9690_five_head_episode_control_target_100m_contract_preflight.json",
    "controller_renderer_preflight": ROOT / "runs/summaries/stage9682_controller_renderer_integration_preflight.json",
    "fixed_template_router": ROOT / "runs/summaries/stage9683_fixed_template_residual_router.json",
    "locked_eval_guard": ROOT / "runs/summaries/stage9688_locked_eval_guard_graph_attachment.json",
}
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DECISION = OUT_DIR / "observe_repair_renderer_reconnect_decision.json"
ROUTING = OUT_DIR / "future_non_template_residual_routing_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OBSERVE_REPAIR_RENDERER_RECONNECT_DECISION_STAGE9691.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def metric(card: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = card
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cards = {name: load_json(path) for name, path in SOURCES.items()}
    failures: list[str] = []
    for name, card in cards.items():
        if card.get("passed") is not True:
            failures.append(f"source_not_passed:{name}")

    strict_joint = metric(cards["observe_repair_promotion"], "metrics", "promotion", "strict_joint_proxy_exact", default=0.0)
    promoted_fields = metric(cards["observe_repair_promotion"], "metrics", "promotion", "fields", default=[])
    contract_loss_counts = metric(cards["guarded_observe_repair_contract"], "metrics", "loss_counts", default={})
    fixed_template_rows = metric(cards["fixed_template_router"], "metrics", "fixed_template_rows", default=-1)
    non_template_queue_rows = metric(cards["fixed_template_router"], "metrics", "non_template_queue_rows", default=-1)
    heldout_renderer_gate_true = metric(cards["controller_renderer_preflight"], "metrics", "heldout_renderer_gate_true_rows", default=0)
    heldout_renderer_rows = metric(cards["controller_renderer_preflight"], "metrics", "heldout_rows", default=-1)

    expected_episode_losses = [
        "episode_boundary_match_ce",
        "episode_failure_type_ce",
        "episode_repair_outcome_ce",
        "episode_step_value_mse",
        "episode_target_prefix_match_ce",
    ]
    missing_episode_losses = [loss for loss in expected_episode_losses if contract_loss_counts.get(loss) != 66]
    forbidden_losses = [loss for loss in ["decoder_ce", "denoise_ce", "runtime_reward"] if contract_loss_counts.get(loss, 0) != 0]
    if strict_joint != 1.0:
        failures.append("observe_repair_strict_joint_not_1")
    if set(promoted_fields) != {"episode_boundary_match", "episode_failure_type", "episode_repair_outcome", "episode_step_value", "episode_target_prefix_match"}:
        failures.append("promoted_fields_mismatch")
    if missing_episode_losses:
        failures.append("guarded_contract_missing_episode_losses")
    if forbidden_losses:
        failures.append("guarded_contract_forbidden_losses_enabled")
    if fixed_template_rows != 26:
        failures.append("fixed_template_rows_not_26")
    if non_template_queue_rows != 0:
        failures.append("non_template_queue_not_empty")
    if heldout_renderer_gate_true != heldout_renderer_rows or heldout_renderer_rows <= 0:
        failures.append("renderer_gate_not_all_heldout")

    decision = {
        "decision": "do_not_authorize_redundant_residual_denoise_execution",
        "reason": "Current residual rows are fixed-template rows already routed to deterministic controller+renderer. Non-template residual queue is empty.",
        "active_route": [
            "five_head_visible_episode_observe_repair_control_v1",
            "slot_template_controller",
            "deterministic_slot_template_renderer",
            "locked_eval_train_exclusion_guard",
        ],
        "blocked_routes_now": [
            "broad_residual_denoise_generation_retry",
            "literal_suffix_choice_prior_generation",
            "decoder_ce_reopen",
            "gemma_or_harness_scoring",
        ],
        "evidence": {
            "observe_repair_strict_joint_proxy_exact": strict_joint,
            "guarded_target_100m_contract_probe_scale": metric(cards["guarded_observe_repair_contract"], "metrics", "probe_scale"),
            "fixed_template_rows": fixed_template_rows,
            "non_template_queue_rows": non_template_queue_rows,
            "heldout_renderer_gate_true_rows": heldout_renderer_gate_true,
            "heldout_renderer_rows": heldout_renderer_rows,
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    routing = {
        "future_non_template_residual_gate_v1": {
            "only_create_denoise_manifest_if": [
                "non_template_queue_rows > 0",
                "row_not_renderable_by_stage9681_template_table",
                "locked_source_exclusion_guard_passed",
                "five_head_observe_repair_control_passed_or_contract_refreshed",
                "decoder_ce == false",
                "runtime == false",
            ],
            "required_row_fields": [
                "row_id",
                "split",
                "language_family",
                "residual_family",
                "observe_repair_control_prediction",
                "renderer_applicability",
                "non_template_reason",
                "loss_mask",
                "authority",
            ],
            "required_audits_before_execution": [
                "locked_source_exclusion_audit",
                "shortcut_baseline_audit",
                "prefix_visibility_audit",
                "repetition_guard_contract",
                "target_100m_contract_only_preflight",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }
    }
    DECISION.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ROUTING.write_text(json.dumps(routing, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = "Select the next real non-template maintainer training package: either mine new non-template residual rows under the Stage9691 gate, or move to source-backed multilingual repo-state/binding/localization task-pack construction for the v2.7 acceptance cells."
    metrics = {
        **dict(AUTHORITY_CLOSED),
        "authority_rows": 0,
        "source_failures": failures,
        "observe_repair_strict_joint_proxy_exact": strict_joint,
        "promoted_field_count": len(promoted_fields),
        "guarded_episode_loss_rows": {loss: contract_loss_counts.get(loss) for loss in expected_episode_losses},
        "forbidden_losses_enabled": forbidden_losses,
        "fixed_template_rows": fixed_template_rows,
        "non_template_queue_rows": non_template_queue_rows,
        "heldout_renderer_gate_true_rows": heldout_renderer_gate_true,
        "heldout_renderer_rows": heldout_renderer_rows,
        "denoise_execution_authorized_next": False,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": metrics,
        "artifacts": {
            "decision": str(DECISION.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "routing_contract": str(ROUTING.relative_to(ROOT)),
        },
        "source_summaries": {name: str(path.relative_to(ROOT)) for name, path in SOURCES.items()},
        "decision": decision["decision"],
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9691 Observe/Repair Renderer Reconnect Decision",
        "",
        f"Passed: `{summary['passed']}`",
        f"Observe/repair strict joint: `{strict_joint}`",
        f"Fixed-template rows: `{fixed_template_rows}`",
        f"Non-template queue rows: `{non_template_queue_rows}`",
        f"Heldout renderer gate: `{heldout_renderer_gate_true}/{heldout_renderer_rows}`",
        "",
        "Decision: do not authorize another residual denoise execution for current fixed-template rows. Use the five-head observe/repair control plus deterministic renderer, and only create a denoise manifest when future non-template residual rows exist.",
        "",
        "No Gemma, harness, runtime, model execution, decoder CE, denoise CE, scoring, source/body emission, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": failures,
        "fixed_template_rows": fixed_template_rows,
        "non_template_queue_rows": non_template_queue_rows,
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
