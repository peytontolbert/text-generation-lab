#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9267
NAME = "stage9267_repetition_to_denoise_repair_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9266_stage9265_stabilized_probe_diagnostic_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9265_stabilized_target_100m_bounded_decoder_probe/bounded_decoder_probe"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9249_semantic_bounded_decoder_target_repair_package/semantic_bounded_decoder_target_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "repetition_to_denoise_repair_manifest.jsonl"
EOS_ROWS = OUT_DIR / "eos_calibration_rows.jsonl"
AUDIT = OUT_DIR / "repetition_to_denoise_repair_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPETITION_TO_DENOISE_REPAIR_MANIFEST_STAGE9267.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUTHORITY_FALSE = dict(AUTHORITY_CLOSED)
FORBIDDEN_KEYS = {
    "source_text",
    "body",
    "raw_body",
    "patch_body",
    "hidden_eval",
    "locked_eval",
    "runtime_output",
    "gemma_output",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def row_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("row_id")): row for row in rows}


def split_for_row(row_id: str, source_by_id: dict[str, dict[str, Any]]) -> str:
    source = source_by_id.get(row_id, {})
    return str(source.get("split") or source.get("package_split") or "eval")


def denoise_split(index: int) -> str:
    return ("train", "eval", "strict_eval")[index % 3]


def build_repair_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows = load_jsonl(SOURCE_MANIFEST)
    source_by_id = row_index(source_rows)
    negative_rows = [row for row in load_jsonl(RUN_DIR / "generated_repetition_negative_rows.jsonl") if row.get("negative_row")]
    samples = load_json(RUN_DIR / "sample_generation_audit.json").get("samples") or []

    repair_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(negative_rows):
        source_id = str(row["row_id"])
        source = source_by_id.get(source_id, {})
        repair_rows.append(
            {
                "row_id": f"stage9267_denoise_repetition_{idx:03d}_{sha(source_id)[:12]}",
                "source_stage": 9265,
                "source_row_id": source_id,
                "source_split": split_for_row(source_id, source_by_id),
                "split": denoise_split(idx),
                "language_family": source.get("language_family") or source.get("language_group") or "unknown",
                "route": "USE_FOR_DENOISE_REPAIR",
                "objective_family": "bounded_decoder_output_repair",
                "repair_task_type": "degenerate_repetition_to_clean_bounded_target",
                "corrupted_output": row["bad_output"],
                "clean_target": row["target_text"],
                "input_state": {
                    "bad_output_hash": sha(row["bad_output"]),
                    "target_hash": sha(row["target_text"]),
                    "failure_type": "degenerate_repetition",
                    "generated_internal_token_leak": False,
                    "decode_allowed": False,
                    "repair_required": True,
                },
                "target": {"decoder_text": row["target_text"]},
                "loss_mask": {
                    "decoder_ce": False,
                    "denoise_ce": True,
                    "runtime_reward": False,
                },
                "authority": AUTHORITY_FALSE,
            }
        )

    eos_rows: list[dict[str, Any]] = []
    for idx, sample in enumerate(samples):
        if sample.get("stopped_on_eos") is True:
            continue
        source_id = str(sample["row_id"])
        source = source_by_id.get(source_id, {})
        eos_rows.append(
            {
                "row_id": f"stage9267_eos_calibration_{idx:03d}_{sha(source_id)[:12]}",
                "source_stage": 9265,
                "source_row_id": source_id,
                "source_split": split_for_row(source_id, source_by_id),
                "split": denoise_split(idx),
                "language_family": source.get("language_family") or source.get("language_group") or "unknown",
                "route": "EOS_CALIBRATION",
                "objective_family": "bounded_decoder_eos_calibration",
                "repair_task_type": "unterminated_generation_to_clean_eos_target",
                "corrupted_output": sample.get("generated_text", ""),
                "clean_target": sample.get("target_text", ""),
                "input_state": {
                    "bad_output_hash": sha(str(sample.get("generated_text", ""))),
                    "target_hash": sha(str(sample.get("target_text", ""))),
                    "failure_type": "unterminated_generation",
                    "generated_token_count": sample.get("generated_token_count"),
                    "max_generation_tokens_hit": True,
                    "decode_allowed": False,
                    "repair_required": True,
                },
                "target": {"decoder_text": str(sample.get("target_text", ""))},
                "loss_mask": {
                    "decoder_ce": False,
                    "denoise_ce": True,
                    "runtime_reward": False,
                },
                "authority": AUTHORITY_FALSE,
            }
        )
    return repair_rows, eos_rows


def audit_rows(repair_rows: list[dict[str, Any]], eos_rows: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    rows = repair_rows + eos_rows
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("source_stage9266_not_passed")
    if (source_summary.get("metrics") or {}).get("quality_gate_passed") is not False:
        failures.append("source_quality_gate_not_failed")
    if len(repair_rows) < 1:
        failures.append("no_repetition_repair_rows")
    if len(eos_rows) < 1:
        failures.append("no_eos_calibration_rows")
    row_ids = [row.get("row_id") for row in rows]
    if len(row_ids) != len(set(row_ids)):
        failures.append("duplicate_row_ids")
    authority_rows = sum(1 for row in rows if any((row.get("authority") or {}).values()))
    if authority_rows:
        failures.append("authority_rows_nonzero")
    unsafe_loss_rows = []
    empty_targets = 0
    forbidden_key_rows = 0
    route_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    for row in rows:
        route_counts[str(row.get("route"))] = route_counts.get(str(row.get("route")), 0) + 1
        language_counts[str(row.get("language_family"))] = language_counts.get(str(row.get("language_family")), 0) + 1
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        if mask.get("denoise_ce") is not True or mask.get("decoder_ce") is not False or mask.get("runtime_reward") is not False:
            unsafe_loss_rows.append(row.get("row_id"))
        if not str((row.get("target") or {}).get("decoder_text", "")).strip():
            empty_targets += 1
        if set(row).intersection(FORBIDDEN_KEYS):
            forbidden_key_rows += 1
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
        "route_counts": route_counts,
        "language_counts": language_counts,
        "split_counts": split_counts,
        "authority": AUTHORITY_FALSE,
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": AUTHORITY_FALSE, "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    repair_rows, eos_rows = build_repair_rows()
    audit = audit_rows(repair_rows, eos_rows, source)
    MANIFEST.write_text("\n".join(json.dumps(row, sort_keys=True) for row in repair_rows + eos_rows) + "\n", encoding="utf-8")
    EOS_ROWS.write_text("\n".join(json.dumps(row, sort_keys=True) for row in eos_rows) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_FALSE,
        "metrics": {**AUTHORITY_FALSE, **audit},
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "eos_rows": str(EOS_ROWS.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Built a denoise repair manifest from Stage9265 repetition failures and unterminated generation rows. No target-100M decoder CE rerun is authorized.",
        "next_best_step": "Run a denoise-repair contract-only preflight over Stage9267, then implement/verify denoise training path before any further bounded decoder CE rerun.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9267 Repetition-To-Denoise Repair Manifest",
                "",
                "Stage9267 converts Stage9265 failed generations into denoise repair rows.",
                "",
                f"Repair rows: {audit['repair_rows']}",
                f"EOS calibration rows: {audit['eos_calibration_rows']}",
                f"Authority rows: {audit['authority_rows']}",
                f"Unsafe loss rows: {audit['unsafe_loss_rows']}",
                "",
                "The manifest enables `denoise_ce` only. Decoder CE, runtime reward, Gemma, harness, scoring, and source/body emission remain closed.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
