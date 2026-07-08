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
STAGE = 9337
NAME = "stage9337_routed_ladder_with_targeted_repair_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9336_targeted_repair_probe_audit.json"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage9331_routed_ladder_suffix_manifest/routed_ladder_suffix_manifest.jsonl"
REPAIR_MANIFEST = ROOT / "runs/local/artifacts/stage9334_targeted_anti_insertion_repetition_manifest/targeted_anti_insertion_repetition_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "routed_ladder_with_targeted_repair_manifest.jsonl"
AUDIT = OUT_DIR / "routed_ladder_with_targeted_repair_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTED_LADDER_WITH_TARGETED_REPAIR_MANIFEST_STAGE9337.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def remap(kind: str, row: dict[str, Any]) -> dict[str, Any]:
    new = json.loads(json.dumps(row))
    new["row_id"] = f"stage9337_{kind}_{row['row_id']}"
    new["source_row_id"] = row["row_id"]
    new["source_stage"] = 9331 if kind == "base" else 9334
    new["merged_curriculum_source"] = kind
    new["objective_family"] = "routed_ladder_with_targeted_repair_denoise"
    new["authority"] = dict(AUTHORITY_CLOSED)
    new["loss_mask"] = {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}
    model_input = new.get("model_input") if isinstance(new.get("model_input"), dict) else {}
    model_input["merged_curriculum_source"] = kind
    model_input["targeted_repair_interference_probe"] = True
    new["model_input"] = model_input
    anti = new.get("anti_cheat") if isinstance(new.get("anti_cheat"), dict) else {}
    anti["decoder_ce_closed"] = True
    anti["runtime_closed"] = True
    anti["merged_targeted_repair_probe"] = True
    new["anti_cheat"] = anti
    return new


def build_rows() -> list[dict[str, Any]]:
    return [remap("base", row) for row in load_jsonl(BASE_MANIFEST)] + [remap("targeted_repair", row) for row in load_jsonl(REPAIR_MANIFEST)]


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    split_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    task_counts: dict[str, int] = {}
    unsafe_rows: list[str] = []
    for row in rows:
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        source_counts[str(row.get("merged_curriculum_source"))] = source_counts.get(str(row.get("merged_curriculum_source")), 0) + 1
        task_counts[str(row.get("repair_task_type"))] = task_counts.get(str(row.get("repair_task_type")), 0) + 1
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if loss.get("decoder_ce") or loss.get("structured_aux") or loss.get("runtime_reward") or not loss.get("denoise_ce"):
            unsafe_rows.append(str(row.get("row_id")))
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(str(row.get("row_id")))
    if source.get("passed") is not True:
        failures.append("source_stage9336_not_passed")
    if len(rows) != 77:
        failures.append("unexpected_row_count")
    if split_counts != {"train": 39, "eval": 22, "strict_eval": 16}:
        failures.append("unexpected_split_counts")
    if source_counts != {"base": 56, "targeted_repair": 21}:
        failures.append("unexpected_source_counts")
    if not {"repair_repeated_keeps_the", "remove_wrong_verified_before_preserves", "repair_operatch_repetition"}.issubset(task_counts):
        failures.append("missing_targeted_repair_tasks")
    if unsafe_rows:
        failures.append("unsafe_rows")
    return {"passed": not failures, "failures": failures, "rows": len(rows), "split_counts": split_counts, "source_counts": source_counts, "task_counts": task_counts, "unsafe_rows": unsafe_rows[:20], "manifest_sha256": sha_file(MANIFEST), "authority": dict(AUTHORITY_CLOSED)}


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
    write_jsonl(MANIFEST, rows)
    audit = audit_rows(rows)
    audit["manifest_sha256"] = sha_file(MANIFEST)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Merged Stage9331 routed ladder rows with Stage9334 targeted repair rows for a controlled interference reprobe.", "next_best_step": "Build Stage9338 preexecution and run a 77-row merged interference probe before reopening any bounded decoder CE path.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9337 Routed Ladder With Targeted Repair Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{audit['split_counts']}`", f"Sources: `{audit['source_counts']}`", "This is the controlled rejoin after Stage9336 solved targeted residual repairs in isolation.", "Decoder CE, runtime, Gemma, harness, source/body emission, scoring, and promotion remain closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": audit["rows"], "split_counts": audit["split_counts"], "source_counts": audit["source_counts"], "failures": audit["failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
