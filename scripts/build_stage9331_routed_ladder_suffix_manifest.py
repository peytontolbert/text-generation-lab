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
STAGE = 9331
NAME = "stage9331_routed_ladder_suffix_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9330_phrase_router_mixture_probe_audit.json"
LADDER = ROOT / "runs/local/artifacts/stage9310_prefix_ladder_supported_suffix_manifest/prefix_ladder_supported_suffix_manifest.jsonl"
ROUTED = ROOT / "runs/local/artifacts/stage9328_phrase_router_mixture_manifest/phrase_router_mixture_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "routed_ladder_suffix_manifest.jsonl"
AUDIT = OUT_DIR / "routed_ladder_suffix_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTED_LADDER_SUFFIX_MANIFEST_STAGE9331.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def remap(source: str, row: dict[str, Any]) -> dict[str, Any]:
    new = json.loads(json.dumps(row))
    new["row_id"] = f"stage9331_{source}_{row['row_id']}"
    new["source_row_id"] = row["row_id"]
    new["source_stage"] = 9310 if source == "ladder" else 9328
    new["combined_curriculum_source"] = source
    new["objective_family"] = "routed_ladder_suffix_denoise"
    new["authority"] = dict(AUTHORITY_CLOSED)
    new["loss_mask"] = {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}
    model_input = new.get("model_input") if isinstance(new.get("model_input"), dict) else {}
    model_input["routed_ladder_source"] = source
    if source == "ladder":
        model_input.setdefault("opaque_phrase_route_id", "route_ladder")
        model_input.setdefault("semantic_surface_kind", str(new.get("input_state", {}).get("surface") if isinstance(new.get("input_state"), dict) else "generic_bounded_argument"))
        model_input.setdefault("anchor_object_kind", str(new.get("input_state", {}).get("anchor_object_kind") if isinstance(new.get("input_state"), dict) else "generic"))
        model_input["route_conditioned"] = False
    new["model_input"] = model_input
    anti_cheat = new.get("anti_cheat") if isinstance(new.get("anti_cheat"), dict) else {}
    anti_cheat["routed_ladder_manifest"] = True
    anti_cheat["decoder_ce_closed"] = True
    new["anti_cheat"] = anti_cheat
    return new


def build_rows() -> list[dict[str, Any]]:
    return [remap("ladder", row) for row in load_jsonl(LADDER)] + [remap("routed_phrase", row) for row in load_jsonl(ROUTED)]


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    split_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    phrase_counts: dict[str, int] = {}
    unsafe_rows: list[str] = []
    suffix_visible_rows: list[str] = []
    for row in rows:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
        source_counts[row["combined_curriculum_source"]] = source_counts.get(row["combined_curriculum_source"], 0) + 1
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        if target.get("phrase_id"):
            phrase_counts[str(target.get("phrase_id"))] = phrase_counts.get(str(target.get("phrase_id")), 0) + 1
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if loss_mask.get("decoder_ce") or loss_mask.get("structured_aux") or not loss_mask.get("denoise_ce"):
            unsafe_rows.append(row["row_id"])
        if any(bool(authority.get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row["row_id"])
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        visible = json.dumps(model_input, sort_keys=True)
        target_text = target.get("decoder_text") if isinstance(target.get("decoder_text"), str) else row.get("clean_target")
        prefix = model_input.get("active_generation_prefix_span")
        if row.get("repair_task_type", "").startswith("clean") and isinstance(target_text, str) and isinstance(prefix, str) and target_text.startswith(prefix):
            suffix = target_text[len(prefix):].strip()
            if suffix and suffix in visible:
                suffix_visible_rows.append(row["row_id"])
    if source.get("passed") is not True or (source.get("metrics") or {}).get("quality_gate_passed") is not True:
        failures.append("source_stage9330_quality_not_passed")
    if len(rows) != 56:
        failures.append("unexpected_row_count")
    if split_counts != {"train": 31, "eval": 13, "strict_eval": 12}:
        failures.append("unexpected_split_counts")
    if source_counts != {"ladder": 32, "routed_phrase": 24}:
        failures.append("unexpected_source_counts")
    if phrase_counts != {"phrase_a": 8, "phrase_b": 8, "phrase_c": 8}:
        failures.append("unexpected_phrase_counts")
    if unsafe_rows:
        failures.append("unsafe_rows")
    if suffix_visible_rows:
        failures.append("suffix_visible_rows")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "source_counts": source_counts,
        "phrase_counts": phrase_counts,
        "unsafe_rows": unsafe_rows[:20],
        "suffix_visible_rows": suffix_visible_rows[:20],
        "manifest_sha256": sha256(MANIFEST),
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
    write_jsonl(MANIFEST, rows)
    audit = audit_rows(rows)
    audit["manifest_sha256"] = sha256(MANIFEST)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Merged the Stage9310 ladder rows with route-conditioned phrase rows for a larger suffix-continuation probe.",
        "next_best_step": "Build Stage9332 preexecution and run the routed ladder suffix probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9331 Routed Ladder Suffix Manifest",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Sources: `{audit['source_counts']}`",
        f"Phrases: `{audit['phrase_counts']}`",
        "This manifest rejoins the successful route-conditioned phrase mixture with the broader prefix ladder.",
        "Decoder CE, runtime, Gemma, harness, source/body emission, scoring, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": audit["rows"], "split_counts": audit["split_counts"], "source_counts": audit["source_counts"], "failures": audit["failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
