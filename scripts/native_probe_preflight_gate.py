from __future__ import annotations

import json
from pathlib import Path
from typing import Any

AUTHORITY_KEYS = (
    "model_execution_authorized_next",
    "decoder_ce_training_authorized_next",
    "runtime_authorized",
    "source_emission_authorized",
    "body_emission_authorized",
    "gemma_execution_authorized_next",
    "harness_execution_authorized_next",
    "scoring_authorized_next",
    "controller_complete_merge_authorized_next",
    "promotion_ready",
)

STRUCTURED_MODES = {
    "structured_policy_probe",
    "symbol_binding_probe",
    "edit_localization_probe",
    "patch_operator_probe",
    "verifier_repair_probe",
}


def _authority(row: dict[str, Any]) -> dict[str, bool]:
    source = row.get("authority") if isinstance(row.get("authority"), dict) else row
    return {key: bool(source.get(key, False)) for key in AUTHORITY_KEYS}


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def audit_preflight_rows(rows: list[dict[str, Any]], *, repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    authority_open_rows: list[str] = []
    missing_gate_rows: list[str] = []
    unsafe_cleanup_rows: list[str] = []
    cap_fail_rows: list[str] = []
    decoder_open_rows: list[str] = []
    missing_required_rows: list[str] = []
    output_path_fail_rows: list[str] = []

    required = {
        "probe_id",
        "mode",
        "source_manifest",
        "output_dir",
        "max_train_rows",
        "max_eval_rows",
        "max_strict_rows",
        "max_steps",
        "post_run_artifact_gate",
        "loss_weights",
        "cleanup_policy",
        "authority",
    }
    for index, row in enumerate(rows):
        row_id = str(row.get("probe_id") or row.get("row_id") or f"row_{index}")
        missing = sorted(key for key in required if key not in row)
        if missing:
            missing_required_rows.append(row_id)
            errors.append(f"{row_id}: missing required fields {missing}")
            continue

        auth = _authority(row)
        if any(auth.values()):
            authority_open_rows.append(row_id)

        mode = str(row.get("mode"))
        weights = row.get("loss_weights") if isinstance(row.get("loss_weights"), dict) else {}
        if mode in STRUCTURED_MODES:
            if float(weights.get("decoder_ce_weight", 0.0)) != 0.0 or float(weights.get("denoise_weight", 0.0)) != 0.0:
                decoder_open_rows.append(row_id)
            if float(weights.get("structured_aux_weight", 0.0)) <= 0.0:
                cap_fail_rows.append(row_id)
        elif mode == "bounded_decoder_ce_probe":
            if float(weights.get("decoder_ce_weight", 0.0)) <= 0.0:
                decoder_open_rows.append(row_id)
        else:
            errors.append(f"{row_id}: unsupported mode {mode}")

        if int(row.get("max_train_rows", 10**9)) > 64 or int(row.get("max_eval_rows", 10**9)) > 32 or int(row.get("max_strict_rows", 10**9)) > 32 or int(row.get("max_steps", 10**9)) > 16:
            cap_fail_rows.append(row_id)

        gate = row.get("post_run_artifact_gate") if isinstance(row.get("post_run_artifact_gate"), dict) else {}
        if gate.get("required") is not True or gate.get("script") != "scripts/native_probe_interpretability_artifact_contract.py":
            missing_gate_rows.append(row_id)
        if mode in STRUCTURED_MODES and gate.get("mode") != "structured_aux_probe":
            missing_gate_rows.append(row_id)
        if mode == "bounded_decoder_ce_probe" and gate.get("mode") != "bounded_decoder_ce_probe":
            missing_gate_rows.append(row_id)

        cleanup = str(row.get("cleanup_policy"))
        if cleanup != "safe_cleanup_checkpoints_only":
            unsafe_cleanup_rows.append(row_id)
        forbidden_paths = set(str(path) for path in row.get("cleanup_forbidden_paths", []))
        if not {"/", "/data", "/arxiv"}.issubset(forbidden_paths):
            unsafe_cleanup_rows.append(row_id)

        out = Path(str(row.get("output_dir")))
        if out.is_absolute():
            resolved_out = out
        else:
            resolved_out = repo_root / out
        if not _is_under(resolved_out, repo_root / "runs" / "local"):
            output_path_fail_rows.append(row_id)

    if authority_open_rows:
        errors.append(f"authority rows open: {authority_open_rows}")
    if decoder_open_rows:
        errors.append(f"forbidden decoder/denoise weights for structured rows: {decoder_open_rows}")
    if cap_fail_rows:
        errors.append(f"probe caps/weights invalid: {sorted(set(cap_fail_rows))}")
    if missing_gate_rows:
        errors.append(f"missing required post-run artifact gate: {sorted(set(missing_gate_rows))}")
    if unsafe_cleanup_rows:
        errors.append(f"unsafe cleanup policy rows: {sorted(set(unsafe_cleanup_rows))}")
    if output_path_fail_rows:
        errors.append(f"output path outside runs/local: {output_path_fail_rows}")

    return {
        "passed": not errors,
        "rows": len(rows),
        "errors": errors,
        "authority_open_rows": authority_open_rows,
        "decoder_open_rows": sorted(set(decoder_open_rows)),
        "cap_fail_rows": sorted(set(cap_fail_rows)),
        "missing_gate_rows": sorted(set(missing_gate_rows)),
        "unsafe_cleanup_rows": sorted(set(unsafe_cleanup_rows)),
        "missing_required_rows": missing_required_rows,
        "output_path_fail_rows": output_path_fail_rows,
        "post_run_artifact_gate_required_rows": sum(1 for row in rows if isinstance(row.get("post_run_artifact_gate"), dict) and row["post_run_artifact_gate"].get("required") is True),
        "model_execution_authorized_now": False,
        "decoder_ce_training_authorized_now": False,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
