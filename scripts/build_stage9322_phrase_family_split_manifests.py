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
STAGE = 9322
NAME = "stage9322_phrase_family_split_manifests"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9321_phrase_completion_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9319_phrase_completion_balance_manifest/phrase_completion_balance_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PHRASE_A_MANIFEST = OUT_DIR / "phrase_a_patch_inside_manifest.jsonl"
PHRASE_B_MANIFEST = OUT_DIR / "phrase_b_patch_operator_manifest.jsonl"
AUDIT = OUT_DIR / "phrase_family_split_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHRASE_FAMILY_SPLIT_MANIFESTS_STAGE9322.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def build_phrase_rows(phrase_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in load_jsonl(SOURCE_MANIFEST):
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        if target.get("phrase_id") != phrase_id:
            continue
        new = json.loads(json.dumps(row))
        new["row_id"] = f"stage9322_{phrase_id}_{row['row_id']}"
        new["source_stage"] = 9319
        new["source_row_id"] = row["row_id"]
        new["objective_family"] = f"{phrase_id}_isolated_phrase_family_denoise"
        new["authority"] = dict(AUTHORITY_CLOSED)
        new["loss_mask"] = {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}
        model_input = new.get("model_input") if isinstance(new.get("model_input"), dict) else {}
        model_input["phrase_family_isolated"] = True
        model_input["target_grounding_mode"] = f"isolated_{model_input.get('target_grounding_mode', 'unknown')}"
        new["model_input"] = model_input
        anti_cheat = new.get("anti_cheat") if isinstance(new.get("anti_cheat"), dict) else {}
        anti_cheat["phrase_family_isolated"] = True
        anti_cheat["decoder_ce_closed"] = True
        new["anti_cheat"] = anti_cheat
        out.append(new)
    return out


def audit_manifest(rows: list[dict[str, Any]], phrase_id: str) -> dict[str, Any]:
    split_counts: dict[str, int] = {}
    variant_counts: dict[str, int] = {}
    unsafe_rows: list[str] = []
    authority_rows: list[str] = []
    suffix_visible_rows: list[str] = []
    for row in rows:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
        variant_counts[row["repair_task_type"]] = variant_counts.get(row["repair_task_type"], 0) + 1
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        if target.get("phrase_id") != phrase_id:
            unsafe_rows.append(row["row_id"])
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        if loss_mask.get("decoder_ce") or loss_mask.get("structured_aux") or not loss_mask.get("denoise_ce"):
            unsafe_rows.append(row["row_id"])
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if any(bool(authority.get(key)) for key in AUTHORITY_CLOSED):
            authority_rows.append(row["row_id"])
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        model_input_text = json.dumps(model_input, sort_keys=True)
        target_text = target.get("decoder_text")
        prefix = model_input.get("active_generation_prefix_span")
        if row.get("repair_task_type") == "clean_prefix_to_phrase_completion" and isinstance(target_text, str) and isinstance(prefix, str) and target_text.startswith(prefix):
            suffix = target_text[len(prefix):].strip()
            if suffix and suffix in model_input_text:
                suffix_visible_rows.append(row["row_id"])
    return {
        "rows": len(rows),
        "split_counts": split_counts,
        "variant_counts": variant_counts,
        "unsafe_rows": unsafe_rows,
        "authority_rows": authority_rows,
        "suffix_visible_rows": suffix_visible_rows,
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
    phrase_a = build_phrase_rows("phrase_a")
    phrase_b = build_phrase_rows("phrase_b")
    write_jsonl(PHRASE_A_MANIFEST, phrase_a)
    write_jsonl(PHRASE_B_MANIFEST, phrase_b)
    audit = {
        "phrase_a": audit_manifest(phrase_a, "phrase_a"),
        "phrase_b": audit_manifest(phrase_b, "phrase_b"),
        "source_stage9321_safety_passed": bool(source.get("passed") is True and (source.get("metrics") or {}).get("safety_gate_passed") is True),
        "phrase_a_manifest_sha256": sha256(PHRASE_A_MANIFEST),
        "phrase_b_manifest_sha256": sha256(PHRASE_B_MANIFEST),
        "authority": dict(AUTHORITY_CLOSED),
    }
    failures: list[str] = []
    if not audit["source_stage9321_safety_passed"]:
        failures.append("source_stage9321_safety_not_passed")
    for phrase_id in ["phrase_a", "phrase_b"]:
        item = audit[phrase_id]
        if item["rows"] != 8:
            failures.append(f"{phrase_id}_row_count_not_8")
        if item["unsafe_rows"]:
            failures.append(f"{phrase_id}_unsafe_rows")
        if item["authority_rows"]:
            failures.append(f"{phrase_id}_authority_rows")
        if item["suffix_visible_rows"]:
            failures.append(f"{phrase_id}_suffix_visible_rows")
    audit["passed"] = not failures
    audit["failures"] = failures
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "phrase_a_manifest": str(PHRASE_A_MANIFEST.relative_to(ROOT)),
            "phrase_b_manifest": str(PHRASE_B_MANIFEST.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Split phrase A and phrase B into isolated denoise manifests to test whether failures are family-local or cross-family interference.",
        "next_best_step": "Run isolated target-100M denoise probes for phrase A and phrase B before any merge back into the combined suffix curriculum.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9322 Phrase Family Split Manifests",
        "",
        f"Passed: `{audit['passed']}`",
        f"Phrase A: `{audit['phrase_a']}`",
        f"Phrase B: `{audit['phrase_b']}`",
        "This stage does not authorize model execution. Decoder CE, runtime, Gemma, harness, source/body emission, scoring, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"phrase_a": audit["phrase_a"], "phrase_b": audit["phrase_b"], "failures": failures}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
