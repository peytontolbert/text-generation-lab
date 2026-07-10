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
STAGE = 9897
NAME = "stage9897_geometry_aware_structured_tiny_execution_review"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9896_v27_geometry_aware_multisurface_compiler_refresh.json"
SOURCE_STRUCTURED = ROOT / "runs/local/artifacts/stage9896_v27_geometry_aware_multisurface_compiler_refresh/compiled/structured_state.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TINY_DIR = OUT_DIR / "tiny_structured_manifests"
TICKET = OUT_DIR / "geometry_aware_structured_tiny_execution_review_inactive.json"
AUDIT = OUT_DIR / "geometry_aware_structured_tiny_execution_review_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GEOMETRY_AWARE_STRUCTURED_TINY_EXECUTION_REVIEW_STAGE9897.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
CAPS = {"train": 32, "eval": 16, "strict_eval": 16}
MAX_STEPS = 8

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
]

REQUIRED_BEFORE_EXECUTION = [
    "fresh_stage9898_capped_contract_only_preflight_passed",
    "explicit_one_run_execution_authorization_after_stage9898",
    "no_runtime_gemma_harness_scoring_source_body_emission",
    "no_final_checkpoint_export",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or "unknown")


def cap_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for split, cap in CAPS.items():
        split_rows = [row for row in rows if str(row.get("split") or "other") == split]
        if len(split_rows) <= cap:
            selected.extend(split_rows)
            continue
        by_language: dict[str, list[dict[str, Any]]] = {}
        language_order: list[str] = []
        for row in split_rows:
            language = row_language(row)
            if language not in by_language:
                by_language[language] = []
                language_order.append(language)
            by_language[language].append(row)
        picked: list[dict[str, Any]] = []
        while len(picked) < cap:
            progressed = False
            for language in language_order:
                bucket = by_language[language]
                if bucket and len(picked) < cap:
                    picked.append(bucket.pop(0))
                    progressed = True
            if not progressed:
                break
        selected.extend(picked)
    return selected


def surface_rows(surface: str) -> list[dict[str, Any]]:
    loss = STRUCTURED_SURFACES[surface]["loss"]
    rows = read_jsonl(SOURCE_STRUCTURED)
    filtered = [row for row in rows if str(row.get("source_skill_area") or "") == surface and str(row.get("expected_enabled_loss") or "") == loss]
    return cap_rows(filtered)


def future_command(surface: str, manifest: Path) -> list[str]:
    spec = STRUCTURED_SURFACES[surface]
    out_dir = f"runs/local/artifacts/stage9899_{surface}_target_100m_structured_tiny_probe/{surface}_probe"
    return [
        "python",
        str(TRAINER.relative_to(ROOT)),
        "--repo-root", str(ROOT),
        "--manifest", str(manifest.relative_to(ROOT)),
        "--mode", str(spec["mode"]),
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", MODEL_CONFIG,
        "--tokenizer-json", TOKENIZER_JSON,
        "--tokenizer-config", TOKENIZER_CONFIG,
        "--tokenizer-hashlock", TOKENIZER_HASHLOCK,
        "--max-train-rows", str(CAPS["train"]),
        "--max-eval-rows", str(CAPS["eval"]),
        "--max-strict-rows", str(CAPS["strict_eval"]),
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
        "--run-id", f"stage9899_{surface}_target_100m_structured_tiny_probe",
        "--execution-authorized-for-recovery-probe",
    ]


def build_ticket(surface_cards: list[dict[str, Any]]) -> dict[str, Any]:
    ticket = {
        "ticket_id": f"{NAME}__inactive",
        "ticket_status": "DESIGN_ONLY_INACTIVE",
        "requested_stage": 9898,
        "requested_stage_name": "stage9898_capped_geometry_aware_structured_target_100m_contract_preflight",
        "requested_capability": "tiny_target_100m_geometry_aware_structured_heads_probe",
        "source_stage": 9896,
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
            "max_train_rows_per_surface": CAPS["train"],
            "max_eval_rows_per_surface": CAPS["eval"],
            "max_strict_rows_per_surface": CAPS["strict_eval"],
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
        "surface_commands": {card["surface"]: future_command(card["surface"], Path(card["manifest"])) for card in surface_cards},
        "surface_cards": surface_cards,
        "authority": dict(AUTHORITY_CLOSED),
    }
    return apply_diagnostic_gate_fields(ticket)


def audit_ticket(ticket: dict[str, Any], source: dict[str, Any], surface_cards: list[dict[str, Any]]) -> dict[str, Any]:
    failures = audit_diagnostic_ticket_fields(ticket)
    if source.get("passed") is not True:
        failures.append("stage9896_not_passed")
    if ticket.get("ticket_status") != "DESIGN_ONLY_INACTIVE":
        failures.append("ticket_not_inactive")
    if ticket.get("execution_authorized_now") is not False or ticket.get("model_execution_authorized_now") is not False:
        failures.append("execution_or_model_authorized_now")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    if sorted(ticket.get("surface_commands") or {}) != sorted(STRUCTURED_SURFACES):
        failures.append("surface_commands_mismatch")
    for item in REQUIRED_BEFORE_EXECUTION:
        if item not in ticket.get("required_before_execution", []):
            failures.append(f"missing_required_before_execution:{item}")
    for card in surface_cards:
        split_counts = card.get("split_counts") if isinstance(card.get("split_counts"), dict) else {}
        if sum(int(value or 0) for value in split_counts.values()) != card.get("rows"):
            failures.append(f"surface_row_total_mismatch:{card.get('surface')}")
        for split, cap in CAPS.items():
            if int(split_counts.get(split, 0) or 0) > cap:
                failures.append(f"surface_cap_exceeded:{card.get('surface')}:{split}")
        if card.get("loss_counts", {}).get(card.get("expected_loss")) != card.get("rows"):
            failures.append(f"surface_loss_count_mismatch:{card.get('surface')}")
    return {"passed": not failures, "failures": failures}


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
    TINY_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    surface_cards: list[dict[str, Any]] = []
    for surface, spec in STRUCTURED_SURFACES.items():
        rows = surface_rows(surface)
        manifest = TINY_DIR / f"{surface}_tiny.jsonl"
        write_jsonl(manifest, rows)
        loss_counts = Counter()
        for row in rows:
            mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
            for key, value in mask.items():
                loss_counts[key] += int(bool(value))
        surface_cards.append({
            "surface": surface,
            "manifest": str(manifest),
            "rows": len(rows),
            "split_counts": dict(Counter(str(row.get("split")) for row in rows)),
            "expected_loss": spec["loss"],
            "loss_counts": dict(sorted((key, value) for key, value in loss_counts.items() if value)),
            "authority": dict(AUTHORITY_CLOSED),
        })
    ticket = build_ticket(surface_cards)
    audit = audit_ticket(ticket, source, surface_cards)
    write_json(TICKET, ticket)
    write_json(AUDIT, audit)
    next_step = "Run Stage9898 capped contract-only preflight on the Stage9897 tiny structured manifests, then execute one capped target-100M structured review on the geometry-aware package."
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
        },
        "artifacts": {
            "ticket": str(TICKET.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "tiny_manifest_dir": str(TINY_DIR.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Prepared capped tiny structured manifests and an inactive execution ticket for the Stage9896 geometry-aware v2.7 package, so the next contract preflight and execution steps use the refreshed edit-localization source rather than the stale packet.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text("\n".join([
        "# Stage9897 Geometry-Aware Structured Tiny Execution Review",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows per surface: `{summary['metrics']['rows_per_surface']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows_per_surface": summary["metrics"]["rows_per_surface"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
