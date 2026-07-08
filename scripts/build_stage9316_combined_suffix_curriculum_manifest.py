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
STAGE = 9316
NAME = "stage9316_combined_suffix_curriculum_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9315_lexical_bridge_contrast_probe_audit.json"
LADDER = ROOT / "runs/local/artifacts/stage9310_prefix_ladder_supported_suffix_manifest/prefix_ladder_supported_suffix_manifest.jsonl"
BRIDGE = ROOT / "runs/local/artifacts/stage9313_lexical_bridge_contrast_manifest/lexical_bridge_contrast_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "combined_suffix_curriculum_manifest.jsonl"
AUDIT = OUT_DIR / "combined_suffix_curriculum_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMBINED_SUFFIX_CURRICULUM_MANIFEST_STAGE9316.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _combined_row(source: str, row: dict[str, Any]) -> dict[str, Any]:
    new_row = json.loads(json.dumps(row))
    new_row["row_id"] = f"stage9316_{source}_{row['row_id']}"
    new_row["source_stage"] = 9310 if source == "ladder" else 9313
    new_row["source_row_id"] = row["row_id"]
    new_row["combined_curriculum_source"] = source
    new_row["objective_family"] = "combined_supported_suffix_and_lexical_bridge_denoise"
    model_input = new_row.get("model_input") if isinstance(new_row.get("model_input"), dict) else {}
    model_input["combined_curriculum_source"] = source
    model_input["target_grounding_mode"] = f"combined_{model_input.get('target_grounding_mode', 'unknown')}"
    new_row["model_input"] = model_input
    anti_cheat = new_row.get("anti_cheat") if isinstance(new_row.get("anti_cheat"), dict) else {}
    anti_cheat["combined_manifest_no_decoder_ce"] = True
    anti_cheat["combined_manifest_source"] = source
    new_row["anti_cheat"] = anti_cheat
    new_row["authority"] = dict(AUTHORITY_CLOSED)
    new_row["loss_mask"] = {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}
    return new_row


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_combined_row("ladder", row) for row in load_jsonl(LADDER))
    rows.extend(_combined_row("bridge", row) for row in load_jsonl(BRIDGE))
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    split_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    prefix_counts: dict[str, int] = {}
    unsafe_loss_rows: list[str] = []
    authority_rows: list[str] = []
    duplicate_ids = len({row["row_id"] for row in rows}) != len(rows)
    suffix_visible_rows: list[str] = []
    for row in rows:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
        source_counts[row["combined_curriculum_source"]] = source_counts.get(row["combined_curriculum_source"], 0) + 1
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        prefix_counts[str(model_input.get("active_generation_prefix_words"))] = prefix_counts.get(str(model_input.get("active_generation_prefix_words")), 0) + 1
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if loss_mask.get("decoder_ce") or loss_mask.get("structured_aux") or not loss_mask.get("denoise_ce"):
            unsafe_loss_rows.append(row["row_id"])
        if any(bool(authority.get(key)) for key in AUTHORITY_CLOSED):
            authority_rows.append(row["row_id"])
        target_text = (row.get("target") or {}).get("decoder_text") if isinstance(row.get("target"), dict) else row.get("clean_target")
        prefix = model_input.get("active_generation_prefix_span")
        visible = json.dumps(model_input, sort_keys=True)
        if isinstance(target_text, str) and isinstance(prefix, str) and target_text.startswith(prefix):
            suffix = target_text[len(prefix):].strip()
            if suffix and suffix in visible and row.get("combined_curriculum_source") == "ladder":
                suffix_visible_rows.append(row["row_id"])
    if source.get("passed") is not True or (source.get("metrics") or {}).get("quality_gate_passed") is not True:
        failures.append("source_stage9315_quality_not_passed")
    if len(rows) != 44:
        failures.append("unexpected_row_count")
    if split_counts != {"train": 27, "eval": 9, "strict_eval": 8}:
        failures.append("unexpected_split_counts")
    if source_counts != {"ladder": 32, "bridge": 12}:
        failures.append("unexpected_source_counts")
    if duplicate_ids:
        failures.append("duplicate_row_ids")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows")
    if authority_rows:
        failures.append("authority_rows")
    if suffix_visible_rows:
        failures.append("target_suffix_visible_in_ladder_rows")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "source_counts": source_counts,
        "prefix_counts": prefix_counts,
        "unsafe_loss_rows": unsafe_loss_rows[:20],
        "authority_rows": authority_rows[:20],
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
        "decision": "Merged the Stage9310 prefix-ladder suffix curriculum with the Stage9313 lexical bridge repair rows without opening decoder CE.",
        "next_best_step": "Build Stage9317 preexecution and run one combined tiny target-100M denoise probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9316 Combined Suffix Curriculum Manifest",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Splits: `{audit['split_counts']}`",
        f"Sources: `{audit['source_counts']}`",
        f"Prefix counts: `{audit['prefix_counts']}`",
        "This is a non-executing manifest merge. Decoder CE, runtime, Gemma, harness, source/body emission, scoring, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": audit["rows"], "split_counts": audit["split_counts"], "source_counts": audit["source_counts"], "failures": audit["failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
