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
STAGE = 9346
NAME = "stage9346_schema_normalized_subword_bridge_repair_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9345_operator_route_rejoin_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9343_full_mixture_with_operator_route_repairs_manifest/full_mixture_with_operator_route_repairs_manifest.jsonl"
SOURCE_RUN = ROOT / "runs/local/artifacts/stage9345_operator_route_rejoin_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "schema_normalized_subword_bridge_repair_manifest.jsonl"
AUDIT = OUT_DIR / "schema_normalized_subword_bridge_repair_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SCHEMA_NORMALIZED_SUBWORD_BRIDGE_REPAIR_MANIFEST_STAGE9346.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_MODEL_FEATURES = ["semantic_surface_kind", "semantic_affordance", "opaque_phrase_route_id", "anchor_object_kind"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def infer_features(target: str, generated: str) -> dict[str, str]:
    lower_target = target.lower()
    lower_generated = generated.lower()
    if "dependency handle" in lower_target:
        return {
            "semantic_surface_kind": "dependency_handle",
            "semantic_affordance": "contain_change_scope",
            "opaque_phrase_route_id": "route_0",
            "anchor_object_kind": "dependency_handle",
            "bridge_error_family": "dependency_handle_keeps_the_bridge",
            "forbidden_fragment": "keepside" if "keepside" in lower_generated else "missing_keeps",
        }
    if "callable endpoint" in lower_target:
        return {
            "semantic_surface_kind": "edit_action_argument",
            "semantic_affordance": "choose_edit_action",
            "opaque_phrase_route_id": "route_1",
            "anchor_object_kind": "callable_endpoint",
            "bridge_error_family": "patch_operator_subword_bridge",
            "forbidden_fragment": "pator",
        }
    if "file path associated" in lower_target:
        return {
            "semantic_surface_kind": "file_path_argument",
            "semantic_affordance": "select_edit_location_path",
            "opaque_phrase_route_id": "route_file_path",
            "anchor_object_kind": "file_path",
            "bridge_error_family": "localized_edit_file_path_bridge",
            "forbidden_fragment": "pator",
        }
    return {
        "semantic_surface_kind": "bounded_argument",
        "semantic_affordance": "repair_subword_bridge",
        "opaque_phrase_route_id": "route_bridge",
        "anchor_object_kind": "bounded_argument",
        "bridge_error_family": "unknown_subword_bridge",
        "forbidden_fragment": "unknown",
    }


def sample_failures() -> list[dict[str, Any]]:
    card = load_json(SOURCE_RUN / "sample_generation_audit.json")
    samples = card.get("samples") if isinstance(card.get("samples"), list) else []
    return [sample for sample in samples if not sample.get("exact_match")]


def build_rows() -> list[dict[str, Any]]:
    source_rows = {str(row.get("row_id")): row for row in load_jsonl(SOURCE_MANIFEST)}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, sample in enumerate(sample_failures()):
        source_id = str(sample.get("row_id"))
        source = source_rows.get(source_id, {})
        target = str(sample.get("target_text") or source.get("clean_target") or "")
        generated = str(sample.get("generated_text") or "")
        prefix = str(sample.get("generation_prefix_text") or "")
        features = infer_features(target, generated)
        row = copy.deepcopy(source) if source else {}
        row_id = f"stage9346_bridge_{idx:03d}_{sha(source_id + generated + target)}"
        if row_id in seen:
            raise ValueError(f"duplicate row_id: {row_id}")
        seen.add(row_id)
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        input_state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        model_input.update(
            {
                "active_generation_prefix_span": prefix,
                "active_generation_prefix_words": len(prefix.split()),
                "bridge_error_family": features["bridge_error_family"],
                "bridge_repair_objective": "schema_normalized_subword_bridge_repair",
                "corrupted_output_fragment": features["forbidden_fragment"],
                "opaque_phrase_route_id": features["opaque_phrase_route_id"],
                "semantic_surface_kind": features["semantic_surface_kind"],
                "semantic_affordance": features["semantic_affordance"],
                "anchor_object_kind": features["anchor_object_kind"],
                "route_schema_version": "stage9346_schema_normalized_v1",
                "clean_target_hidden_from_model_input": True,
                "remaining_suffix_hidden_from_model_input": True,
                "first_suffix_word_hidden_from_model_input": True,
            }
        )
        for forbidden_key in ["clean_target", "target_text", "target_phrase", "remaining_suffix", "first_suffix_word"]:
            model_input.pop(forbidden_key, None)
        input_state.update(
            {
                "source_stage9345_row_id": source_id,
                "source_stage9345_generated_sha256": hashlib.sha256(generated.encode("utf-8")).hexdigest(),
                "target_text_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
                "bridge_error_family": features["bridge_error_family"],
                "decode_allowed": False,
                "repair_required": True,
                "target_remainder_hidden": True,
                "target_suffix_hidden": True,
                "remaining_suffix_hidden_from_model_input": True,
            }
        )
        anti_cheat.update(
            {
                "decoder_ce_closed": True,
                "runtime_closed": True,
                "clean_target_in_model_input": False,
                "remaining_suffix_visible": False,
                "schema_normalized_bridge_repair": True,
            }
        )
        row.update(
            {
                "row_id": row_id,
                "source_stage": STAGE,
                "source_stage9345_row_id": source_id,
                "split": sample.get("split") or source.get("split") or "train",
                "language_family": source.get("language_family") or "unknown",
                "merged_curriculum_source": "schema_normalized_subword_bridge_repair",
                "combined_curriculum_source": "subword_bridge_repair",
                "repair_task_type": features["bridge_error_family"],
                "clean_target": target,
                "corrupted_output": generated,
                "model_input": model_input,
                "input_state": input_state,
                "anti_cheat": anti_cheat,
                "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
                "authority": dict(AUTHORITY_CLOSED),
            }
        )
        rows.append(row)
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(str(row.get("split")) for row in rows)
    task_counts = Counter(str(row.get("repair_task_type")) for row in rows)
    route_counts = Counter(str(row.get("model_input", {}).get("opaque_phrase_route_id")) for row in rows)
    surface_counts = Counter(str(row.get("model_input", {}).get("semantic_surface_kind")) for row in rows)
    missing_features: list[str] = []
    unsafe_rows: list[str] = []
    target_visible_rows: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if any(not mi.get(feature) for feature in REQUIRED_MODEL_FEATURES):
            missing_features.append(row_id)
        if loss != {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}:
            unsafe_rows.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row_id)
        target = str(row.get("clean_target") or "")
        model_input_text = json.dumps(mi, sort_keys=True)
        if target and target in model_input_text:
            target_visible_rows.append(row_id)
    failures: list[str] = []
    if len(rows) != 31:
        failures.append("unexpected_row_count")
    if split_counts != {"train": 17, "eval": 10, "strict_eval": 4}:
        failures.append("unexpected_split_counts")
    if set(task_counts) != {"dependency_handle_keeps_the_bridge", "patch_operator_subword_bridge", "localized_edit_file_path_bridge"}:
        failures.append("missing_expected_bridge_tasks")
    if missing_features:
        failures.append("missing_required_model_features")
    if unsafe_rows:
        failures.append("unsafe_rows")
    if target_visible_rows:
        failures.append("target_visible_in_model_input")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "task_counts": dict(sorted(task_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "surface_counts": dict(sorted(surface_counts.items())),
        "missing_feature_rows": missing_features,
        "unsafe_rows": sorted(set(unsafe_rows)),
        "target_visible_rows": target_visible_rows,
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
    source = load_json(SOURCE_SUMMARY)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    audit = audit_rows(rows)
    if source.get("passed") is not False or source.get("metrics", {}).get("safety_gate_passed") is not True:
        audit["passed"] = False
        audit.setdefault("failures", []).append("source_stage9345_not_safe_failed_audit")
    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": bool(audit["passed"]),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built denoise-only repair rows for Stage9345 subword bridge failures with normalized route/surface/affordance features.",
        "next_best_step": "Build Stage9347 preexecution for a tiny Stage9348 schema-normalized subword bridge repair probe; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9346 Schema-Normalized Subword Bridge Repair Manifest",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{audit['split_counts']}`",
                f"Tasks: `{audit['task_counts']}`",
                f"Routes: `{audit['route_counts']}`",
                f"Surfaces: `{audit['surface_counts']}`",
                "",
                "This manifest converts Stage9345 exact-match failures into denoise-only repair rows. It normalizes the model-visible route/surface/affordance schema and trains only the corrupted-output-to-clean-target repair transition.",
                "",
                "Decoder CE, runtime, harness, Gemma, scoring, source/body emission, checkpoint export, controller merge, and promotion remain closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "split_counts", "task_counts", "route_counts", "surface_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
