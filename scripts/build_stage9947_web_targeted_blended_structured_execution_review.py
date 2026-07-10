#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED, apply_diagnostic_gate_fields, audit_diagnostic_ticket_fields
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED, apply_diagnostic_gate_fields, audit_diagnostic_ticket_fields  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9947
NAME = "stage9947_web_targeted_blended_structured_execution_review"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9946_web_targeted_blended_target100m_contract_preflight.json"
BLEND_AUDIT = ROOT / "runs/local/artifacts/stage9945_web_targeted_blended_structured_mix/web_targeted_blended_structured_mix_audit.json"
SOURCE_MANIFEST_DIR = ROOT / "runs/local/artifacts/stage9946_web_targeted_blended_target100m_contract_preflight/manifests"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REVIEW_DIR = OUT_DIR / "review_manifests"
TICKET = OUT_DIR / "web_targeted_blended_structured_execution_review_inactive.json"
AUDIT = OUT_DIR / "web_targeted_blended_structured_execution_review_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEB_TARGETED_BLENDED_STRUCTURED_EXECUTION_REVIEW_STAGE9947.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
MAX_STEPS = 64

STRUCTURED_SURFACES = {
    "symbol_binding": {"mode": "symbol_binding_probe", "loss": "symbol_binding_ce"},
    "edit_localization": {"mode": "edit_localization_probe", "loss": "edit_localization_ce"},
    "patch_operator_selection": {"mode": "patch_operator_probe", "loss": "patch_operator_ce"},
    "verifier_failure_repair_or_abstain": {"mode": "verifier_repair_probe", "loss": "verifier_repair_ce"},
}

DENIED_NOW_OPERATIONS = [
    "run_trainer",
    "instantiate_model",
    "run_model_forward",
    "run_training_step",
    "run_backward",
    "create_optimizer",
    "generate_model_output",
    "write_checkpoint",
    "export_checkpoint",
    "open_runtime",
    "call_gemma",
    "run_harness",
    "score_output",
    "emit_source_body",
    "promote_model",
    "walk_arxiv",
    "mine_repositories",
    "cleanup_checkpoints_outside_safe_cleanup",
]

REQUIRED_BEFORE_EXECUTION = [
    "fresh_stage9946_blended_contract_only_preflight_passed",
    "explicit_one_run_execution_authorization_after_stage9947",
    "disk_free_space_preflight_passed",
    "safe_cleanup_marker_and_dry_run_passed",
    "run_uses_stage9945_blended_structured_state_or_stage9946_manifests_only",
    "preserve_targeted_web_refresh_rows_inside_edit_localization_surface",
    "no_bounded_decoder_ce_in_this_probe",
    "no_runtime_gemma_harness_scoring_source_body_emission",
    "post_run_stage8902_diagnostics_required",
    "stage8903_diagnostics_closure_required",
    "metrics_interpretation_blocked_until_diagnostics_pass",
    "no_final_checkpoint_export",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("split") or "other") for row in rows)
    known = {"train", "eval", "strict_eval"}
    return {
        "train": counts.get("train", 0),
        "eval": counts.get("eval", 0),
        "strict_eval": counts.get("strict_eval", 0),
        "other": sum(count for split, count in counts.items() if split not in known),
    }


def build_surface_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for surface, spec in STRUCTURED_SURFACES.items():
        source_manifest = SOURCE_MANIFEST_DIR / f"{surface}.jsonl"
        rows = read_jsonl(source_manifest)
        review_manifest = REVIEW_DIR / f"{surface}.jsonl"
        write_jsonl(review_manifest, rows)
        loss_counts = Counter()
        language_counts = Counter()
        for row in rows:
            language = str(row.get("language_family") or row.get("language") or "unknown")
            language_counts[language] += 1
            mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
            for key, value in mask.items():
                loss_counts[key] += int(bool(value))
        cards.append({
            "surface": surface,
            "manifest": display(review_manifest),
            "source_manifest": display(source_manifest),
            "rows": len(rows),
            "split_counts": split_counts(rows),
            "expected_loss": spec["loss"],
            "loss_counts": dict(sorted((key, value) for key, value in loss_counts.items() if value)),
            "language_counts": dict(sorted((key, value) for key, value in language_counts.items() if value)),
            "authority": dict(AUTHORITY_CLOSED),
        })
    return cards


def future_command(card: dict[str, Any]) -> list[str]:
    surface = str(card["surface"])
    spec = STRUCTURED_SURFACES[surface]
    counts = card["split_counts"]
    out_dir = f"runs/local/artifacts/stage9948_{surface}_web_targeted_blended_target100m_probe/{surface}_probe"
    return [
        "python",
        str(TRAINER.relative_to(ROOT)),
        "--repo-root", str(ROOT),
        "--manifest", str(card["manifest"]),
        "--mode", str(spec["mode"]),
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", MODEL_CONFIG,
        "--tokenizer-json", TOKENIZER_JSON,
        "--tokenizer-config", TOKENIZER_CONFIG,
        "--tokenizer-hashlock", TOKENIZER_HASHLOCK,
        "--max-train-rows", str(counts["train"]),
        "--max-eval-rows", str(counts["eval"]),
        "--max-strict-rows", str(counts["strict_eval"]),
        "--max-steps", str(MAX_STEPS),
        "--batch-size", "2",
        "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0",
        "--structured-aux-weight", "1.0",
        "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save", "1",
        "--output-dir", out_dir,
        "--run-id", f"stage9948_{surface}_web_targeted_blended_target100m_probe",
        "--execution-authorized-for-recovery-probe",
    ]


def build_ticket(surface_cards: list[dict[str, Any]], blend_audit: dict[str, Any]) -> dict[str, Any]:
    edit_card = next(card for card in surface_cards if card["surface"] == "edit_localization")
    metrics = blend_audit.get("metrics") if isinstance(blend_audit.get("metrics"), dict) else {}
    ticket = {
        "ticket_id": f"{NAME}__inactive",
        "ticket_status": "DESIGN_ONLY_INACTIVE",
        "requested_stage": 9948,
        "requested_stage_name": "stage9948_web_targeted_blended_structured_target100m_probe_series",
        "requested_capability": "blended_multilingual_target_100m_structured_heads_probe_with_web_recovery_rows",
        "source_stage": 9946,
        "blend_source_stage": 9945,
        "command_materialized_for_review_only": True,
        "command_executable_now": False,
        "execution_authorized_now": False,
        "model_execution_authorized_now": False,
        "decoder_ce_training_authorized_now": False,
        "allowed_operations_now": [],
        "denied_operations_now": list(DENIED_NOW_OPERATIONS),
        "required_before_execution": list(REQUIRED_BEFORE_EXECUTION),
        "required_limits": {
            "surfaces": sorted(STRUCTURED_SURFACES),
            "excluded_surfaces": ["bounded_argument_rendering"],
            "max_steps_per_surface": MAX_STEPS,
            "decoder_ce_weight": 0.0,
            "structured_aux_weight": 1.0,
            "denoise_weight": 0.0,
            "runtime": False,
            "gemma": False,
            "harness": False,
            "scoring": False,
            "source_body_emission": False,
            "final_checkpoint_export": False,
            "cleanup_checkpoints_after_probe": True,
        },
        "blend_context": {
            "base_structured_rows": metrics.get("base_structured_rows"),
            "blended_structured_rows": metrics.get("blended_structured_rows"),
            "targeted_web_rows_added": metrics.get("targeted_web_rows_added"),
            "targeted_web_weight_sum": metrics.get("targeted_web_weight_sum"),
            "web_edit_rows_before": metrics.get("web_edit_rows_before"),
            "web_edit_rows_after": metrics.get("web_edit_rows_after"),
            "edit_localization_web_rows_in_review_manifest": edit_card["language_counts"].get("web_js_ts_html", 0),
        },
        "surface_commands": {card["surface"]: future_command(card) for card in surface_cards},
        "surface_cards": surface_cards,
        "authority": dict(AUTHORITY_CLOSED),
    }
    return apply_diagnostic_gate_fields(ticket)


def audit_ticket(ticket: dict[str, Any], source: dict[str, Any], blend_audit: dict[str, Any], surface_cards: list[dict[str, Any]]) -> dict[str, Any]:
    failures = audit_diagnostic_ticket_fields(ticket)
    if source.get("passed") is not True:
        failures.append("stage9946_not_passed")
    if blend_audit.get("passed") is not True:
        failures.append("stage9945_not_passed")
    if ticket.get("ticket_status") != "DESIGN_ONLY_INACTIVE":
        failures.append("ticket_not_inactive")
    if ticket.get("execution_authorized_now") is not False or ticket.get("model_execution_authorized_now") is not False:
        failures.append("execution_or_model_authorized_now")
    if ticket.get("decoder_ce_training_authorized_now") is not False:
        failures.append("decoder_ce_authorized_now")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    if sorted(ticket.get("surface_commands") or {}) != sorted(STRUCTURED_SURFACES):
        failures.append("surface_commands_mismatch")
    for item in REQUIRED_BEFORE_EXECUTION:
        if item not in ticket.get("required_before_execution", []):
            failures.append(f"missing_required_before_execution:{item}")
    total_rows = 0
    for card in surface_cards:
        counts = card.get("split_counts") if isinstance(card.get("split_counts"), dict) else {}
        if sum(int(value or 0) for value in counts.values()) != int(card.get("rows") or 0):
            failures.append(f"surface_row_total_mismatch:{card.get('surface')}")
        if int(counts.get("other", 0) or 0) != 0:
            failures.append(f"surface_has_other_split_rows:{card.get('surface')}")
        if card.get("loss_counts", {}).get(card.get("expected_loss")) != card.get("rows"):
            failures.append(f"surface_loss_count_mismatch:{card.get('surface')}")
        if any(value for value in card.get("authority", {}).values()):
            failures.append(f"surface_authority_open:{card.get('surface')}")
        total_rows += int(card.get("rows") or 0)
    blend_context = ticket.get("blend_context") if isinstance(ticket.get("blend_context"), dict) else {}
    if blend_context.get("blended_structured_rows") != total_rows:
        failures.append("blended_total_rows_mismatch")
    if blend_context.get("targeted_web_rows_added") != 12:
        failures.append("targeted_web_rows_added_not_12")
    if blend_context.get("web_edit_rows_after") != 27:
        failures.append("web_edit_rows_after_not_27")
    if blend_context.get("edit_localization_web_rows_in_review_manifest") != 27:
        failures.append("review_manifest_web_edit_rows_not_27")
    return {"passed": not failures, "failures": failures}


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    blend_audit = load_json(BLEND_AUDIT)
    surface_cards = build_surface_cards()
    ticket = build_ticket(surface_cards, blend_audit)
    audit = audit_ticket(ticket, source, blend_audit, surface_cards)
    TICKET.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use this inactive review ticket to authorize one blended target-100M structured probe series that preserves the targeted web refresh rows from Stage9945 and the contract-validated manifests from Stage9946."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "failures": audit["failures"],
            "surface_count": len(surface_cards),
            "rows_per_surface": {card["surface"]: card["rows"] for card in surface_cards},
            "total_rows": sum(int(card["rows"]) for card in surface_cards),
            "web_edit_rows_in_review_manifest": next(
                int(card["language_counts"].get("web_js_ts_html", 0))
                for card in surface_cards
                if card["surface"] == "edit_localization"
            ),
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "decoder_ce_training_authorized_now": False,
            "bounded_decoder_excluded": True,
        },
        "artifacts": {
            "ticket": display(TICKET),
            "audit": display(AUDIT),
            "review_manifest_dir": display(REVIEW_DIR),
            "doc": display(DOC),
        },
        "decision": "Built an inactive execution-review ticket for the Stage9945/9946 blended multilingual structured mix so the next target-100M run stays tied to the web-recovered edit-localization surface and the validated contract-only manifests.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9947 Web-Targeted Blended Structured Execution Review",
        "",
        f"Passed: `{summary['passed']}`",
        f"Surfaces: `{sorted(STRUCTURED_SURFACES)}`",
        f"Rows per surface: `{summary['metrics']['rows_per_surface']}`",
        f"Web edit rows in review manifest: `{summary['metrics']['web_edit_rows_in_review_manifest']}`",
        "Execution authorized now: `False`",
        "Bounded decoder CE included: `False`",
        "",
        "This is an inactive review card. It materializes the blended structured manifests and future commands for the next target-100M run, but it does not execute trainer work.",
        "",
        "No runtime, source/body emission, Gemma, harness, scoring, model execution, decoder CE, denoise CE, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": audit["failures"],
        "total_rows": summary["metrics"]["total_rows"],
        "web_edit_rows_in_review_manifest": summary["metrics"]["web_edit_rows_in_review_manifest"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
