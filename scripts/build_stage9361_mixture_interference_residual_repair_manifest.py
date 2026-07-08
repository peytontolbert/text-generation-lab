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
STAGE = 9361
NAME = "stage9361_mixture_interference_residual_repair_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9360_non_operator_rejoin_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9358_full_mixture_with_non_operator_residual_repairs_manifest/full_mixture_with_non_operator_residual_repairs_manifest.jsonl"
SOURCE_RUN = ROOT / "runs/local/artifacts/stage9360_non_operator_rejoin_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "mixture_interference_residual_repair_manifest.jsonl"
AUDIT = OUT_DIR / "mixture_interference_residual_repair_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MIXTURE_INTERFERENCE_RESIDUAL_REPAIR_MANIFEST_STAGE9361.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def residual_type(target: str, generated: str) -> str:
    if target.endswith("verified patch operator") and "pator" in generated:
        return "operator_pator_subword_terminal_repair"
    if target.endswith("verified patch operator") and "verified" not in generated:
        return "operator_verified_omission_repair"
    if target.endswith("localized edit") and "patch inside" in generated:
        return "file_path_patch_inside_intrusion_repair"
    if target.endswith("localized edit") and "localized edit" not in generated:
        return "file_path_localized_edit_omission_repair"
    return "mixture_interference_exact_residual_repair"


def build_rows() -> list[dict[str, Any]]:
    source_rows = {str(row.get("row_id")): row for row in load_jsonl(SOURCE_MANIFEST)}
    samples = load_json(SOURCE_RUN / "sample_generation_audit.json").get("samples", [])
    rows: list[dict[str, Any]] = []
    for idx, sample in enumerate(samples):
        if sample.get("exact_match") and not sample.get("degenerate_repetition") and not sample.get("short_or_junk") and not sample.get("empty_output"):
            continue
        source_id = str(sample.get("row_id"))
        source = source_rows[source_id]
        row = copy.deepcopy(source)
        target = str(sample.get("target_text") or source.get("clean_target") or "")
        generated = str(sample.get("generated_text") or "")
        prefix = str(sample.get("generation_prefix_text") or "")
        task = residual_type(target, generated)
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        row_id = f"stage9361_mixture_residual_{idx:03d}_{h(source_id + generated)}"
        mi.update(
            {
                "active_generation_prefix_span": prefix,
                "active_generation_prefix_words": len(prefix.split()),
                "bridge_error_family": task,
                "bridge_repair_objective": "mixture_interference_residual_repair",
                "corrupted_output_fragment": generated[-72:],
                "clean_target_hidden_from_model_input": True,
                "remaining_suffix_hidden_from_model_input": True,
                "first_suffix_word_hidden_from_model_input": True,
                "route_schema_version": "stage9361_mixture_interference_residual_v1",
            }
        )
        for key in ["clean_target", "target_text", "target_phrase", "remaining_suffix", "first_suffix_word"]:
            mi.pop(key, None)
        state.update(
            {
                "source_stage9360_row_id": source_id,
                "source_stage9360_generated_sha256": hashlib.sha256(generated.encode("utf-8")).hexdigest(),
                "target_text_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
                "mixture_interference_residual_repair_required": True,
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
                "mixture_interference_residual_repair": True,
            }
        )
        row.update(
            {
                "row_id": row_id,
                "source_stage": STAGE,
                "source_stage9360_row_id": source_id,
                "split": sample.get("split") or source.get("split"),
                "merged_curriculum_source": "mixture_interference_residual_repair",
                "combined_curriculum_source": "mixture_interference_residual_repair",
                "repair_task_type": task,
                "clean_target": target,
                "corrupted_output": generated,
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
    task_counts = Counter(str(row.get("repair_task_type")) for row in rows)
    route_counts = Counter(str(row.get("model_input", {}).get("opaque_phrase_route_id")) for row in rows)
    surface_counts = Counter(str(row.get("model_input", {}).get("semantic_surface_kind")) for row in rows)
    unsafe: list[str] = []
    target_visible: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if loss != {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}:
            unsafe.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe.append(row_id)
        if str(row.get("clean_target") or "") in json.dumps(mi, sort_keys=True):
            target_visible.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not False or metrics.get("safety_gate_passed") is not True:
        failures.append("source_stage9360_not_safe_failed_audit")
    if len(rows) != 55:
        failures.append("unexpected_row_count")
    if dict(split_counts) != {"train": 27, "eval": 17, "strict_eval": 11}:
        failures.append("unexpected_split_counts")
    if dict(route_counts) != {"route_1": 49, "route_file_path": 6}:
        failures.append("unexpected_route_counts")
    if unsafe:
        failures.append("unsafe_rows")
    if target_visible:
        failures.append("target_visible_in_model_input")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "task_counts": dict(sorted(task_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "surface_counts": dict(sorted(surface_counts.items())),
        "unsafe_rows": sorted(set(unsafe))[:20],
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
    DOC.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    audit = audit_rows(rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": bool(audit["passed"]),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built denoise-only rows for Stage9360 full-mixture interference residuals.",
        "next_best_step": "Build Stage9362 preexecution for a 55-row mixture-interference residual probe; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9361 Mixture Interference Residual Repair Manifest",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{audit['split_counts']}`",
                f"Tasks: `{audit['task_counts']}`",
                f"Routes: `{audit['route_counts']}`",
                f"Surfaces: `{audit['surface_counts']}`",
                "",
                "This manifest isolates the Stage9360 rejoin residuals: route_1 `verified patch operator` omissions/subword drift and route_file_path `localized edit` drift.",
                "Decoder CE, runtime, harness, Gemma, scoring, promotion, and checkpoint export remain closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "split_counts", "task_counts", "route_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
