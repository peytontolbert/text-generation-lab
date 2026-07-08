#!/usr/bin/env python3
from __future__ import annotations

import copy
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
STAGE = 9385
NAME = "stage9385_prefix_primed_bounded_decoder_failure_denoise_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9384_bounded_decoder_failure_denoise_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9382_bounded_decoder_failure_to_denoise_manifest/bounded_decoder_failure_to_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "prefix_primed_bounded_decoder_failure_denoise_manifest.jsonl"
AUDIT = OUT_DIR / "prefix_primed_bounded_decoder_failure_denoise_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PREFIX_PRIMED_BOUNDED_DECODER_FAILURE_DENOISE_MANIFEST_STAGE9385.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def active_prefix(target: str) -> str:
    words = target.split()
    return " ".join(words[: min(7, max(4, len(words) // 4))])


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, source in enumerate(load_jsonl(SOURCE_MANIFEST)):
        row = copy.deepcopy(source)
        target = str(row.get("clean_target") or (row.get("target") or {}).get("decoder_text") or "")
        prefix = active_prefix(target)
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        row_id = f"stage9385_prefix_denoise_{idx:03d}_{h(str(row.get('row_id')) + prefix)}"
        mi.update(
            {
                "active_generation_prefix_span": prefix,
                "active_generation_prefix_words": len(prefix.split()),
                "bridge_repair_objective": "prefix_primed_bounded_decoder_failure_denoise",
                "bridge_error_family": row.get("repair_task_type"),
                "bridge_priming_then_continue": True,
                "clean_target_hidden_from_model_input": True,
                "remaining_suffix_hidden_from_model_input": True,
                "first_suffix_word_hidden_from_model_input": True,
                "source_stage9382_row_id": row.get("row_id"),
                "route_schema_version": "stage9385_prefix_primed_bounded_decoder_failure_v1",
            }
        )
        for key in ["clean_target", "target_text", "target_phrase", "remaining_suffix", "first_suffix_word"]:
            mi.pop(key, None)
        state.update(
            {
                "source_stage9382_row_id": row.get("row_id"),
                "target_text_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
                "prefix_primed_repair_required": True,
                "decode_allowed": False,
                "repair_required": True,
                "target_remainder_hidden": True,
                "target_suffix_hidden": True,
            }
        )
        anti.update(
            {
                "decoder_ce_closed": True,
                "runtime_closed": True,
                "clean_target_in_model_input": False,
                "remaining_suffix_visible": False,
                "prefix_primed_bounded_decoder_failure_repair": True,
            }
        )
        row.update(
            {
                "row_id": row_id,
                "source_stage": STAGE,
                "source_stage9382_row_id": row.get("row_id"),
                "merged_curriculum_source": "prefix_primed_bounded_decoder_failure_denoise",
                "combined_curriculum_source": "prefix_primed_bounded_decoder_failure_denoise",
                "repair_task_type": f"prefix_primed_{row.get('repair_task_type')}",
                "clean_target": target,
                "model_input": mi,
                "input_state": state,
                "anti_cheat": anti,
                "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
                "authority": dict(AUTHORITY_CLOSED),
            }
        )
        rows.append(row)
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    split_counts = Counter(str(row.get("split")) for row in rows)
    route_counts = Counter(str(row.get("route")) for row in rows)
    unsafe: list[str] = []
    target_visible: list[str] = []
    missing_prefix: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        target = str(row.get("clean_target") or "")
        prefix = str(mi.get("active_generation_prefix_span") or "")
        if loss != {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}:
            unsafe.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe.append(row_id)
        if not prefix or not target.startswith(prefix):
            missing_prefix.append(row_id)
        if target and target in json.dumps(mi, sort_keys=True):
            target_visible.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not False or metrics.get("safety_gate_passed") is not True:
        failures.append("source_stage9384_not_safe_failed_audit")
    if len(rows) != 23:
        failures.append("unexpected_row_count")
    if dict(split_counts) != {"train": 7, "eval": 9, "strict_eval": 7}:
        failures.append("unexpected_split_counts")
    if dict(route_counts) != {"EOS_CALIBRATION": 11, "USE_FOR_DENOISE_REPAIR": 12}:
        failures.append("unexpected_route_counts")
    if unsafe:
        failures.append("unsafe_rows")
    if missing_prefix:
        failures.append("missing_or_invalid_active_prefix")
    if target_visible:
        failures.append("target_visible_in_model_input")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "unsafe_rows": sorted(set(unsafe))[:20],
        "missing_prefix_rows": missing_prefix[:20],
        "target_visible_rows": target_visible[:20],
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
    rows = build_rows()
    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    audit = audit_rows(rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built prefix-primed denoise rows for Stage9384 bounded-decoder failure repairs, using the active_generation_prefix_span pattern that passed the Stage9369-9378 repair chain.",
        "next_best_step": "Build Stage9386 preexecution for the 23-row prefix-primed denoise probe; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9385 Prefix-Primed Bounded Decoder Failure Denoise Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{audit['split_counts']}`", f"Routes: `{audit['route_counts']}`", "", "This keeps decoder CE closed and exposes only a short active generation prefix, not the full target.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "split_counts", "route_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
