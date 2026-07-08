#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9382
NAME = "stage9382_bounded_decoder_failure_to_denoise_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9381_bounded_decoder_ce_probe_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9381_bounded_decoder_ce_probe"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9249_semantic_bounded_decoder_target_repair_package/semantic_bounded_decoder_target_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "bounded_decoder_failure_to_denoise_manifest.jsonl"
EOS_ROWS = OUT_DIR / "bounded_decoder_eos_calibration_rows.jsonl"
AUDIT = OUT_DIR / "bounded_decoder_failure_to_denoise_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_FAILURE_TO_DENOISE_MANIFEST_STAGE9382.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FORBIDDEN_KEYS = {"source_text", "body", "raw_body", "patch_body", "hidden_eval", "locked_eval", "runtime_output", "gemma_output"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def denoise_split(index: int) -> str:
    return ("train", "eval", "strict_eval")[index % 3]


def build_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows = {str(row.get("row_id")): row for row in load_jsonl(SOURCE_MANIFEST)}
    negative_rows = [row for row in load_jsonl(RUN_DIR / "generated_repetition_negative_rows.jsonl") if row.get("negative_row")]
    samples = load_json(RUN_DIR / "sample_generation_audit.json").get("samples") or []
    repair_rows: list[dict[str, Any]] = []
    for idx, neg in enumerate(negative_rows):
        source_id = str(neg["row_id"])
        source = source_rows.get(source_id, {})
        bad_output = str(neg.get("bad_output", ""))
        target = str(neg.get("target_text", ""))
        repair_rows.append(
            {
                "row_id": f"stage9382_denoise_repetition_{idx:03d}_{sha(source_id)[:12]}",
                "source_stage": 9381,
                "source_row_id": source_id,
                "source_split": source.get("split") or "eval",
                "split": denoise_split(idx),
                "language_family": source.get("language_family") or "unknown",
                "route": "USE_FOR_DENOISE_REPAIR",
                "objective_family": "bounded_decoder_output_repair",
                "repair_task_type": "stage9381_degeneration_to_clean_bounded_target",
                "corrupted_output": bad_output,
                "clean_target": target,
                "input_state": {
                    "bad_output_hash": sha(bad_output),
                    "target_hash": sha(target),
                    "failure_type": "degenerate_repetition",
                    "generated_internal_token_leak": False,
                    "decode_allowed": False,
                    "repair_required": True,
                    "source_bounded_decoder_probe": "stage9381",
                },
                "target": {"decoder_text": target},
                "loss_mask": {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False},
                "authority": dict(AUTHORITY_CLOSED),
            }
        )
    eos_rows: list[dict[str, Any]] = []
    for idx, sample in enumerate(samples):
        if not sample.get("unterminated") and sample.get("stopped_on_eos") is True:
            continue
        source_id = str(sample.get("row_id"))
        source = source_rows.get(source_id, {})
        generated = str(sample.get("generated_text", ""))
        target = str(sample.get("target_text", ""))
        eos_rows.append(
            {
                "row_id": f"stage9382_eos_calibration_{idx:03d}_{sha(source_id)[:12]}",
                "source_stage": 9381,
                "source_row_id": source_id,
                "source_split": source.get("split") or sample.get("split") or "eval",
                "split": denoise_split(idx),
                "language_family": source.get("language_family") or "unknown",
                "route": "EOS_CALIBRATION",
                "objective_family": "bounded_decoder_eos_calibration",
                "repair_task_type": "stage9381_unterminated_generation_to_clean_eos_target",
                "corrupted_output": generated,
                "clean_target": target,
                "input_state": {
                    "bad_output_hash": sha(generated),
                    "target_hash": sha(target),
                    "failure_type": "unterminated_generation",
                    "max_generation_tokens_hit": True,
                    "decode_allowed": False,
                    "repair_required": True,
                    "source_bounded_decoder_probe": "stage9381",
                },
                "target": {"decoder_text": target},
                "loss_mask": {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False},
                "authority": dict(AUTHORITY_CLOSED),
            }
        )
    return repair_rows, eos_rows


def audit_rows(repair_rows: list[dict[str, Any]], eos_rows: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    rows = repair_rows + eos_rows
    failures: list[str] = []
    metrics = source_summary.get("metrics") if isinstance(source_summary.get("metrics"), dict) else {}
    if source_summary.get("passed") is not False or metrics.get("safety_gate_passed") is not True:
        failures.append("source_stage9381_not_safe_failed_audit")
    if metrics.get("quality_gate_passed") is not False:
        failures.append("source_quality_gate_not_failed")
    if len(repair_rows) != 12:
        failures.append("unexpected_repair_row_count")
    if len(eos_rows) != 11:
        failures.append("unexpected_eos_row_count")
    row_ids = [str(row.get("row_id")) for row in rows]
    if len(row_ids) != len(set(row_ids)):
        failures.append("duplicate_row_ids")
    authority_rows = sum(1 for row in rows if any((row.get("authority") or {}).values()))
    unsafe_loss_rows = []
    empty_targets = 0
    forbidden_key_rows = 0
    route_counts = Counter(str(row.get("route")) for row in rows)
    language_counts = Counter(str(row.get("language_family")) for row in rows)
    split_counts = Counter(str(row.get("split")) for row in rows)
    for row in rows:
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        if mask.get("denoise_ce") is not True or mask.get("decoder_ce") is not False or mask.get("runtime_reward") is not False:
            unsafe_loss_rows.append(str(row.get("row_id")))
        if not str((row.get("target") or {}).get("decoder_text", "")).strip():
            empty_targets += 1
        if set(row).intersection(FORBIDDEN_KEYS):
            forbidden_key_rows += 1
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows_nonzero")
    if empty_targets:
        failures.append("empty_targets_nonzero")
    if forbidden_key_rows:
        failures.append("forbidden_key_rows_nonzero")
    serialized = json.dumps(rows, sort_keys=True).lower()
    for token in ["/arxiv", "hidden_eval", "locked_eval", "runtime_authorized\": true", "gemma_execution_authorized_next\": true"]:
        if token in serialized:
            failures.append(f"forbidden_token:{token}")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "repair_rows": len(repair_rows),
        "eos_calibration_rows": len(eos_rows),
        "authority_rows": authority_rows,
        "unsafe_loss_rows": len(unsafe_loss_rows),
        "empty_targets": empty_targets,
        "forbidden_key_rows": forbidden_key_rows,
        "route_counts": dict(sorted(route_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    repair_rows, eos_rows = build_rows()
    audit = audit_rows(repair_rows, eos_rows, source)
    rows = repair_rows + eos_rows
    MANIFEST.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    EOS_ROWS.write_text("\n".join(json.dumps(row, sort_keys=True) for row in eos_rows) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "eos_rows": str(EOS_ROWS.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a denoise-only repair manifest from Stage9381 bounded decoder CE repetition and unterminated failures. No decoder CE rerun is authorized.",
        "next_best_step": "Build a Stage9383 denoise preexecution over the 23-row bounded decoder failure repair manifest; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9382 Bounded Decoder Failure-To-Denoise Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Repair rows: `{audit['repair_rows']}`", f"EOS calibration rows: `{audit['eos_calibration_rows']}`", f"Routes: `{audit['route_counts']}`", f"Languages: `{audit['language_counts']}`", "", "The bounded decoder CE probe remains quality-blocked. These rows route repetition and unterminated failures back into the denoise repair loop, with decoder CE and external authority closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "repair_rows", "eos_calibration_rows", "route_counts", "language_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
