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
STAGE = 9319
NAME = "stage9319_phrase_completion_balance_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9318_combined_suffix_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "phrase_completion_balance_manifest.jsonl"
AUDIT = OUT_DIR / "phrase_completion_balance_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHRASE_COMPLETION_BALANCE_MANIFEST_STAGE9319.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PHRASES = [
    {
        "opaque_phrase_id": "phrase_a",
        "external_label": "dependency_patch_inside",
        "language_family": "web_js_ts_html",
        "target": "Emit the dependency handle that keeps the patch inside",
        "prefixes": [
            "Emit the dependency handle that",
            "Emit the dependency handle that keeps",
            "Emit the dependency handle that keeps the",
            "Emit the dependency handle that keeps the patch",
        ],
        "bad_outputs": [
            "Emit the dependency handle that  the patch ins the patch inside",
            "Emit the dependency handle that keeps the patch ins the patch inside",
            "Emit the dependency handle that keeps the patch ins the patch ins the patch inside",
            "Emit the dependency handle that keeps the patch ins the verified patch inside",
        ],
    },
    {
        "opaque_phrase_id": "phrase_b",
        "external_label": "verified_patch_operator",
        "language_family": "cpp",
        "target": "Select the callable endpoint that the verified patch operator",
        "prefixes": [
            "Select the callable endpoint that",
            "Select the callable endpoint that the",
            "Select the callable endpoint that the verified",
            "Select the callable endpoint that the verified patch",
        ],
        "bad_outputs": [
            "Select the callable endpoint that the verified pator",
            "Select the callable endpoint that verified patch operatch operatch operator",
            "Select the callable endpoint that the expected assertion",
            "Select the callable endpoint that the verified patch operatch operator",
        ],
    },
    {
        "opaque_phrase_id": "phrase_c",
        "external_label": "constant_preserves_expected_assertion",
        "language_family": "python",
        "target": "Select the small constant that preserves the expected assertion",
        "prefixes": [
            "Select the small constant that",
            "Select the small constant that preserves",
            "Select the small constant that preserves the",
            "Select the small constant that preserves the expected",
        ],
        "bad_outputs": [
            "Select the small constant that the localizhedcal expected assertion",
            "Select the small constant that the expected assertion",
            "Select the small constant that preserves localizhedcal assertion",
            "Select the small constant that preserves the patch operator",
        ],
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def split_for(index: int) -> str:
    return ["train", "eval", "strict_eval"][index % 3]


def clean_prefix_row(spec: dict[str, Any], index: int, prefix: str, global_index: int) -> dict[str, Any]:
    return {
        "row_id": f"stage9319_clean_{spec['opaque_phrase_id']}_{index}_{sha256_text(prefix)}",
        "split": split_for(global_index),
        "objective_family": "phrase_completion_balance_denoise",
        "repair_task_type": "clean_prefix_to_phrase_completion",
        "route": "USE_FOR_DENOISE_REPAIR",
        "language_family": spec["language_family"],
        "input_state": {
            "phrase_id": spec["opaque_phrase_id"],
            "target_shape": "bounded_decoder_argument",
            "decoder_budget_ok": True,
            "authority_closed": True,
        },
        "model_input": {
            "active_generation_prefix_span": prefix,
            "active_generation_prefix_words": len(prefix.split()),
            "target_grounding_mode": "phrase_completion_balance_v1",
            "phrase_id": spec["opaque_phrase_id"],
            "remaining_suffix_hidden_from_model_input": True,
            "external_label_hidden": True,
        },
        "corrupted_output": prefix,
        "clean_target": spec["target"],
        "target": {"decoder_text": spec["target"], "phrase_id": spec["opaque_phrase_id"]},
        "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
        "authority": dict(AUTHORITY_CLOSED),
        "anti_cheat": {
            "no_target_suffix_in_model_input": True,
            "external_label_not_model_visible": True,
            "source_body_absent": True,
            "decoder_ce_closed": True,
        },
        "source_stage": 9318,
    }


def bad_output_row(spec: dict[str, Any], index: int, bad: str, global_index: int) -> dict[str, Any]:
    prefix = " ".join(spec["target"].split()[:5])
    return {
        "row_id": f"stage9319_bad_{spec['opaque_phrase_id']}_{index}_{sha256_text(bad)}",
        "split": split_for(global_index),
        "objective_family": "phrase_completion_balance_denoise",
        "repair_task_type": "observed_or_synthetic_phrase_error_to_clean_target",
        "route": "USE_FOR_DENOISE_REPAIR",
        "language_family": spec["language_family"],
        "input_state": {
            "phrase_id": spec["opaque_phrase_id"],
            "failure_type": "phrase_completion_interference",
            "target_shape": "bounded_decoder_argument",
            "decoder_budget_ok": True,
            "authority_closed": True,
        },
        "model_input": {
            "active_generation_prefix_span": prefix,
            "active_generation_prefix_words": len(prefix.split()),
            "target_grounding_mode": "phrase_completion_bad_output_repair_v1",
            "phrase_id": spec["opaque_phrase_id"],
            "bad_output_visible_for_repair": True,
            "external_label_hidden": True,
        },
        "corrupted_output": bad,
        "clean_target": spec["target"],
        "target": {"decoder_text": spec["target"], "phrase_id": spec["opaque_phrase_id"]},
        "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
        "authority": dict(AUTHORITY_CLOSED),
        "anti_cheat": {
            "bad_output_visible_as_corruption": True,
            "external_label_not_model_visible": True,
            "source_body_absent": True,
            "decoder_ce_closed": True,
        },
        "source_stage": 9318,
    }


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    i = 0
    for spec in PHRASES:
        for j, prefix in enumerate(spec["prefixes"]):
            rows.append(clean_prefix_row(spec, j, prefix, i))
            i += 1
        for j, bad in enumerate(spec["bad_outputs"]):
            rows.append(bad_output_row(spec, j, bad, i))
            i += 1
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    split_counts: dict[str, int] = {}
    phrase_counts: dict[str, int] = {}
    variant_counts: dict[str, int] = {}
    unsafe_loss_rows: list[str] = []
    authority_rows: list[str] = []
    suffix_visible_rows: list[str] = []
    for row in rows:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
        phrase_id = row["target"]["phrase_id"]
        phrase_counts[phrase_id] = phrase_counts.get(phrase_id, 0) + 1
        variant_counts[row["repair_task_type"]] = variant_counts.get(row["repair_task_type"], 0) + 1
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        model_input_text = json.dumps(model_input, sort_keys=True)
        target = row["target"]["decoder_text"]
        prefix = model_input.get("active_generation_prefix_span")
        if row["repair_task_type"] == "clean_prefix_to_phrase_completion" and isinstance(prefix, str) and target.startswith(prefix):
            suffix = target[len(prefix):].strip()
            if suffix and suffix in model_input_text:
                suffix_visible_rows.append(row["row_id"])
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        if loss_mask.get("decoder_ce") or loss_mask.get("structured_aux") or not loss_mask.get("denoise_ce"):
            unsafe_loss_rows.append(row["row_id"])
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if any(bool(authority.get(key)) for key in AUTHORITY_CLOSED):
            authority_rows.append(row["row_id"])
    if source.get("passed") is not True or (source.get("metrics") or {}).get("safety_gate_passed") is not True:
        failures.append("source_stage9318_safety_not_passed")
    if len(rows) != 24:
        failures.append("unexpected_row_count")
    if split_counts != {"train": 8, "eval": 8, "strict_eval": 8}:
        failures.append("unexpected_split_counts")
    if phrase_counts != {"phrase_a": 8, "phrase_b": 8, "phrase_c": 8}:
        failures.append("unexpected_phrase_counts")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows")
    if authority_rows:
        failures.append("authority_rows")
    if suffix_visible_rows:
        failures.append("target_suffix_visible_in_clean_rows")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "phrase_counts": phrase_counts,
        "variant_counts": variant_counts,
        "unsafe_loss_rows": unsafe_loss_rows,
        "authority_rows": authority_rows,
        "suffix_visible_rows": suffix_visible_rows,
        "manifest_sha256": sha256_file(MANIFEST),
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
    audit["manifest_sha256"] = sha256_file(MANIFEST)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized a balanced phrase-completion denoise manifest for the Stage9318 combined-curriculum interference failures.",
        "next_best_step": "Build a preexecution stage for a tiny phrase-completion probe, then merge only if it repairs all three phrase families.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9319 Phrase Completion Balance Manifest",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Splits: `{audit['split_counts']}`",
        f"Phrase counts: `{audit['phrase_counts']}`",
        f"Variant counts: `{audit['variant_counts']}`",
        "This targets the Stage9318 interference families with balanced phrase IDs: dependency `patch inside`, callable `patch operator`, and constant `preserves expected assertion`.",
        "No model execution, decoder CE, runtime, Gemma, harness, source/body emission, scoring, or promotion is authorized.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": audit["rows"], "split_counts": audit["split_counts"], "phrase_counts": audit["phrase_counts"], "failures": audit["failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
