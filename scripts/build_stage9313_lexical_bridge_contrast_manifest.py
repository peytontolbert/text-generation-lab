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
STAGE = 9313
NAME = "stage9313_lexical_bridge_contrast_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9312_prefix_ladder_supported_suffix_probe_audit.json"
RUN_AUDIT = ROOT / "runs/local/artifacts/stage9312_prefix_ladder_supported_suffix_probe/stage9312_prefix_ladder_supported_suffix_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "lexical_bridge_contrast_manifest.jsonl"
AUDIT = OUT_DIR / "lexical_bridge_contrast_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LEXICAL_BRIDGE_CONTRAST_MANIFEST_STAGE9313.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BRIDGE_SPECS = [
    {
        "bridge_family": "bridge_a",
        "bridge_description": "keeps_to_keeps_the_patch_inside",
        "language_family": "web_js_ts_html",
        "surface": "dependency_handle",
        "target": "Emit the dependency handle that keeps the patch inside",
        "bad_outputs": ["Emit the dependency handle that keepside"],
        "prefixes": [
            "Emit the dependency handle that",
            "Emit the dependency handle that keeps",
            "Emit the dependency handle that keeps the",
            "Emit the dependency handle that keeps the patch",
        ],
        "required_continuations": ["keeps the patch inside", "the patch inside", "patch inside", "inside"],
        "forbidden_continuations": ["keepside", "keeps inside"],
    },
    {
        "bridge_family": "bridge_b",
        "bridge_description": "verified_patch_operator",
        "language_family": "cpp",
        "surface": "patch_operator_argument",
        "target": "Select the callable endpoint that the verified patch operator",
        "bad_outputs": [
            "Select the callable endpoint that verified patch operatch operatch operatch operatch operatch operator",
            "Select the callable endpoint that the expected assertion",
            "Select the callable endpoint that the verified patch operatch operatch operatch operatch operatch operator",
        ],
        "prefixes": [
            "Select the callable endpoint that",
            "Select the callable endpoint that the",
            "Select the callable endpoint that the verified",
            "Select the callable endpoint that the verified patch",
        ],
        "required_continuations": ["the verified patch operator", "verified patch operator", "patch operator", "operator"],
        "forbidden_continuations": ["verified patch operatch", "expected assertion", "patch operatch"],
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _split_for(index: int) -> str:
    return ["train", "eval", "strict_eval"][index % 3]


def _row_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    i = 0
    for spec in BRIDGE_SPECS:
        for prefix_index, prefix in enumerate(spec["prefixes"]):
            clean_row_id = f"stage9313_clean_{spec['bridge_family']}_{prefix_index}_{_row_id(prefix)}"
            rows.append({
                "row_id": clean_row_id,
                "split": _split_for(i),
                "objective_family": "bounded_decoder_argument_lexical_bridge_contrast",
                "repair_task_type": "clean_prefix_to_required_bridge_continuation",
                "route": "USE_FOR_DENOISE_REPAIR",
                "language_family": spec["language_family"],
                "input_state": {
                    "surface": spec["surface"],
                    "bridge_family": spec["bridge_family"],
                    "target_shape": "bounded_decoder_argument",
                    "authority_closed": True,
                    "decoder_budget_ok": True,
                },
                "model_input": {
                    "active_generation_prefix_span": prefix,
                    "active_generation_prefix_words": len(prefix.split()),
                    "target_grounding_mode": "lexical_bridge_contrast_v1",
                    "remaining_suffix_hidden_from_model_input": True,
                    "bridge_family": spec["bridge_family"],
                    "forbidden_continuation_count": len(spec["forbidden_continuations"]),
                    "required_continuation_hint_masked": True,
                },
                "corrupted_output": prefix,
                "clean_target": spec["target"],
                "target": {"decoder_text": spec["target"], "bridge_family": spec["bridge_family"]},
                "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
                "authority": dict(AUTHORITY_CLOSED),
                "anti_cheat": {
                    "no_target_suffix_in_model_input": True,
                    "forbidden_bad_continuations_visible_only_as_negative_constraints": True,
                    "source_body_absent": True,
                    "decoder_ce_closed": True,
                },
                "source_stage": 9312,
            })
            i += 1
        for bad_index, bad in enumerate(spec["bad_outputs"]):
            repair_row_id = f"stage9313_observed_bad_{spec['bridge_family']}_{bad_index}_{_row_id(bad)}"
            rows.append({
                "row_id": repair_row_id,
                "split": _split_for(i),
                "objective_family": "bounded_decoder_argument_lexical_bridge_contrast",
                "repair_task_type": "observed_bad_bridge_to_clean_target",
                "route": "USE_FOR_DENOISE_REPAIR",
                "language_family": spec["language_family"],
                "input_state": {
                    "surface": spec["surface"],
                    "bridge_family": spec["bridge_family"],
                    "failure_type": "subword_bridge_collapse_or_wrong_lexical_continuation",
                    "target_shape": "bounded_decoder_argument",
                    "authority_closed": True,
                    "decoder_budget_ok": True,
                },
                "model_input": {
                    "active_generation_prefix_span": bad,
                    "active_generation_prefix_words": len(bad.split()),
                    "target_grounding_mode": "lexical_bridge_bad_output_repair_v1",
                    "bad_output_visible_for_repair": True,
                    "bridge_family": spec["bridge_family"],
                    "forbidden_continuation_count": len(spec["forbidden_continuations"]),
                },
                "corrupted_output": bad,
                "clean_target": spec["target"],
                "target": {"decoder_text": spec["target"], "bridge_family": spec["bridge_family"]},
                "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
                "authority": dict(AUTHORITY_CLOSED),
                "anti_cheat": {
                    "bad_output_visible_as_corruption": True,
                    "clean_target_suffix_not_in_model_input": bad != spec["target"],
                    "source_body_absent": True,
                    "decoder_ce_closed": True,
                },
                "source_stage": 9312,
            })
            i += 1
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    run_audit = load_json(RUN_AUDIT)
    failures: list[str] = []
    suffix_visible_rows: list[str] = []
    unsafe_loss_rows: list[str] = []
    authority_rows: list[str] = []
    bridge_counts: dict[str, int] = {}
    variant_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    for row in rows:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
        bridge = row["target"]["bridge_family"]
        bridge_counts[bridge] = bridge_counts.get(bridge, 0) + 1
        variant = row["repair_task_type"]
        variant_counts[variant] = variant_counts.get(variant, 0) + 1
        model_input_text = json.dumps(row.get("model_input", {}), sort_keys=True)
        target_text = row["target"]["decoder_text"]
        prefix = row["model_input"]["active_generation_prefix_span"]
        suffix = target_text[len(prefix):].strip() if target_text.startswith(prefix) else target_text
        if suffix and suffix in model_input_text and not row["repair_task_type"].startswith("observed_bad"):
            suffix_visible_rows.append(row["row_id"])
        loss_mask = row.get("loss_mask") or {}
        if loss_mask.get("decoder_ce") or loss_mask.get("structured_aux") or not loss_mask.get("denoise_ce"):
            unsafe_loss_rows.append(row["row_id"])
        if any(bool(row.get("authority", {}).get(key)) for key in AUTHORITY_CLOSED):
            authority_rows.append(row["row_id"])
    if source.get("passed") is not True or run_audit.get("safety_gate_passed") is not True:
        failures.append("source_stage9312_safety_not_passed")
    if suffix_visible_rows:
        failures.append("target_suffix_visible_in_clean_prefix_rows")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows")
    if authority_rows:
        failures.append("authority_rows")
    if len(rows) != 12:
        failures.append("unexpected_row_count")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "bridge_counts": bridge_counts,
        "variant_counts": variant_counts,
        "suffix_visible_rows": suffix_visible_rows,
        "unsafe_loss_rows": unsafe_loss_rows,
        "authority_rows": authority_rows,
        "authority": dict(AUTHORITY_CLOSED),
        "next_patch_target": "stage9314_preexecution_for_lexical_bridge_contrast_probe",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


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
        "decision": "Materialized a tiny non-executing lexical bridge contrast manifest for the Stage9312 suffix failures.",
        "next_best_step": "Build Stage9314 preexecution for a tiny lexical bridge contrast denoise probe; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9313 Lexical Bridge Contrast Manifest",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Bridge counts: `{audit['bridge_counts']}`",
        f"Variant counts: `{audit['variant_counts']}`",
        "Bridge IDs are opaque in model-visible fields: `bridge_a` and `bridge_b`.",
        "Externally, these target the two Stage9312 residual failures: `keeps` -> `keeps the patch inside` and `verified patch operator` vs `operatch`/`expected assertion`.",
        "No model execution, decoder CE, runtime, Gemma, harness, source/body emission, scoring, or promotion is authorized.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": audit["rows"], "bridge_counts": audit["bridge_counts"], "variant_counts": audit["variant_counts"], "failures": audit["failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
