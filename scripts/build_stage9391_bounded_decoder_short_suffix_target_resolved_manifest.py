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
STAGE = 9391
NAME = "stage9391_bounded_decoder_short_suffix_target_resolved_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9390_bounded_decoder_short_suffix_bridge_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9388_bounded_decoder_short_suffix_bridge_manifest/bounded_decoder_short_suffix_bridge_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "bounded_decoder_short_suffix_target_resolved_manifest.jsonl"
AUDIT = OUT_DIR / "bounded_decoder_short_suffix_target_resolved_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_SHORT_SUFFIX_TARGET_RESOLVED_MANIFEST_STAGE9391.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, source in enumerate(load_jsonl(SOURCE_MANIFEST)):
        row = copy.deepcopy(source)
        short_target = str(row.get("clean_target") or "")
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        short_sha = hashlib.sha256(short_target.encode("utf-8")).hexdigest()
        row_id = f"stage9391_short_suffix_resolved_{idx:03d}_{h(str(row.get('row_id')) + short_sha)}"
        mi.update(
            {
                "target_resolver_repaired": True,
                "target_surface": "short_suffix_target_only",
                "source_stage9388_row_id": row.get("row_id"),
                "route_schema_version": "stage9391_bounded_decoder_short_suffix_target_resolved_v1",
            }
        )
        for key in ["clean_target", "target_text", "target_phrase", "remaining_suffix", "first_suffix_word", "original_full_target"]:
            mi.pop(key, None)
        state.update(
            {
                "source_stage9388_row_id": row.get("row_id"),
                "target_hash": short_sha,
                "target_text_sha256": short_sha,
                "short_target_sha256": short_sha,
                "full_target_replaced_by_short_target": True,
            }
        )
        anti.update({"decoder_ce_closed": True, "runtime_closed": True, "target_resolver_repaired": True})
        row.update(
            {
                "row_id": row_id,
                "source_stage": STAGE,
                "source_stage9388_row_id": row.get("row_id"),
                "merged_curriculum_source": "bounded_decoder_short_suffix_target_resolved",
                "combined_curriculum_source": "bounded_decoder_short_suffix_target_resolved",
                "repair_task_type": "bounded_decoder_short_suffix_target_resolved",
                "clean_target": short_target,
                "decoder_text": short_target,
                "target": {"decoder_text": short_target},
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
    inconsistent_target: list[str] = []
    target_visible: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        target = str(row.get("clean_target") or "")
        nested = row.get("target") if isinstance(row.get("target"), dict) else {}
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        prefix = str(mi.get("active_generation_prefix_span") or "")
        if loss != {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}:
            unsafe.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe.append(row_id)
        if not target or nested.get("decoder_text") != target or row.get("decoder_text") != target or not target.startswith(prefix):
            inconsistent_target.append(row_id)
        if target and target in json.dumps(mi, sort_keys=True):
            target_visible.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not False or metrics.get("safety_gate_passed") is not True:
        failures.append("source_stage9390_not_safe_failed_audit")
    if len(rows) != 23:
        failures.append("unexpected_row_count")
    if dict(split_counts) != {"eval": 9, "strict_eval": 7, "train": 7}:
        failures.append("unexpected_split_counts")
    if dict(route_counts) != {"EOS_CALIBRATION": 11, "USE_FOR_DENOISE_REPAIR": 12}:
        failures.append("unexpected_route_counts")
    if unsafe:
        failures.append("unsafe_rows")
    if inconsistent_target:
        failures.append("inconsistent_target_surfaces")
    if target_visible:
        failures.append("target_visible_in_model_input")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "unsafe_rows": sorted(set(unsafe))[:20],
        "inconsistent_target_rows": inconsistent_target[:20],
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
        "decision": "Resolved Stage9388 target surfaces so the trainer sees only the short suffix target, not the original full bounded decoder target.",
        "next_best_step": "Build Stage9392 preexecution for the target-resolved short-suffix bridge probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9391 Bounded Decoder Short-Suffix Target-Resolved Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{audit['split_counts']}`",
                f"Routes: `{audit['route_counts']}`",
                "",
                "`clean_target`, `decoder_text`, and `target.decoder_text` now all point to the short suffix target.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "split_counts", "route_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
