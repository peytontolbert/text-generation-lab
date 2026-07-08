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
STAGE = 9340
NAME = "stage9340_operator_route_separation_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9339_merged_repair_interference_probe_audit.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9339_merged_repair_interference_probe/stage9339_merged_repair_interference_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9337_routed_ladder_with_targeted_repair_manifest/routed_ladder_with_targeted_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "operator_route_separation_manifest.jsonl"
AUDIT = OUT_DIR / "operator_route_separation_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_ROUTE_SEPARATION_MANIFEST_STAGE9340.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def normalize_operator_route(row: dict[str, Any], failure: dict[str, Any], idx: int) -> dict[str, Any]:
    new = json.loads(json.dumps(row))
    generated = str(failure.get("generated") or new.get("corrupted_output") or "")
    target = str(failure.get("target") or new.get("clean_target") or (new.get("target") or {}).get("decoder_text") or "")
    labels = [str(x) for x in failure.get("labels", []) if isinstance(x, str)]
    model_input = new.get("model_input") if isinstance(new.get("model_input"), dict) else {}
    model_input.update({
        "bad_output_text": generated,
        "bad_output_sha256": sha_text(generated),
        "clean_target_sha256": sha_text(target),
        "decoder_repair_mode": "operator_route_separated_bad_output_repair",
        "error_signature": "+".join(labels) if labels else "operator_route_failure",
        "forbidden_error_patterns": labels,
        "opaque_phrase_route_id": "route_1",
        "phrase_id": "phrase_b",
        "route_conditioned": True,
        "routed_ladder_source": "operator_route_repair",
        "semantic_affordance": "choose_edit_action",
        "semantic_surface_kind": "edit_action_argument",
        "anchor_object_kind": "callable_endpoint",
        "target_grounding_mode": "operator_route_separation_repair_v1",
        "target_text_hidden_except_hash": True,
    })
    new.update({
        "row_id": f"stage9340_operator_{idx:03d}_{sha_text(str(new.get('row_id')) + generated)}",
        "source_stage": 9339,
        "source_row_id": row.get("row_id"),
        "source_split": failure.get("split"),
        "objective_family": "operator_route_separation_denoise",
        "repair_task_type": "operator_route_separated_repair",
        "route": "USE_FOR_DENOISE_REPAIR",
        "language_family": "cpp",
        "combined_curriculum_source": "operator_route_separation",
        "merged_curriculum_source": "operator_route_separation",
        "corrupted_output": generated,
        "clean_target": target,
        "model_input": model_input,
        "target": {"decoder_text": target, "phrase_id": "phrase_b"},
        "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
        "authority": dict(AUTHORITY_CLOSED),
        "anti_cheat": {"decoder_ce_closed": True, "runtime_closed": True, "operator_route_id_is_semantic_not_label": True, "target_text_hidden_except_hash": True, "bad_output_visible_for_repair_objective": True},
    })
    input_state = new.get("input_state") if isinstance(new.get("input_state"), dict) else {}
    input_state.update({"repair_required": True, "decoder_budget_ok": True, "decode_allowed": False, "target_shape": "bounded_decoder_argument", "route_separation_required": True})
    new["input_state"] = input_state
    return new


def file_path_repair(row: dict[str, Any], failure: dict[str, Any], idx: int) -> dict[str, Any]:
    generated = str(failure.get("generated") or "")
    target = str(failure.get("target") or row.get("clean_target") or "Select the file path associated with the localized edit")
    prefix = "Select the file path associated"
    return {
        "row_id": f"stage9340_filepath_{idx:03d}_{sha_text(str(row.get('row_id')) + generated)}",
        "source_stage": 9339,
        "source_row_id": row.get("row_id"),
        "source_split": failure.get("split"),
        "split": failure.get("split") or row.get("split") or "train",
        "objective_family": "operator_route_separation_denoise",
        "repair_task_type": "repair_file_path_associated_with",
        "route": "USE_FOR_DENOISE_REPAIR",
        "language_family": row.get("language_family") or "python",
        "combined_curriculum_source": "file_path_route_separation",
        "merged_curriculum_source": "file_path_route_separation",
        "corrupted_output": generated,
        "clean_target": target,
        "input_state": {"repair_required": True, "decoder_budget_ok": True, "decode_allowed": False, "target_shape": "bounded_decoder_argument", "route_separation_required": True},
        "model_input": {
            "active_generation_prefix_span": prefix,
            "active_generation_prefix_words": 5,
            "bad_output_text": generated,
            "bad_output_sha256": sha_text(generated),
            "clean_target_sha256": sha_text(target),
            "decoder_repair_mode": "file_path_preposition_repair",
            "error_signature": "associated_lis",
            "forbidden_error_patterns": ["associated_lis"],
            "opaque_phrase_route_id": "route_file_path",
            "phrase_id": "file_path_associated_with",
            "route_conditioned": True,
            "semantic_affordance": "select_edit_location_path",
            "semantic_surface_kind": "file_path_argument",
            "anchor_object_kind": "file_path",
            "target_grounding_mode": "file_path_associated_with_repair_v1",
            "target_text_hidden_except_hash": True,
        },
        "target": {"decoder_text": target, "phrase_id": "file_path_associated_with"},
        "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
        "authority": dict(AUTHORITY_CLOSED),
        "anti_cheat": {"decoder_ce_closed": True, "runtime_closed": True, "target_text_hidden_except_hash": True, "bad_output_visible_for_repair_objective": True},
    }


def split_balance(rows: list[dict[str, Any]]) -> None:
    # Preserve observed failure split when possible, then ensure all three splits exist.
    seen = {row.get("split") for row in rows}
    needed = [s for s in ["train", "eval", "strict_eval"] if s not in seen]
    for row, split in zip(rows, needed):
        row["split"] = split


def build_rows() -> list[dict[str, Any]]:
    source_audit = load_json(SOURCE_AUDIT)
    manifest = {str(row.get("row_id")): row for row in load_jsonl(SOURCE_MANIFEST)}
    failures = source_audit.get("failed_samples") if isinstance(source_audit.get("failed_samples"), list) else []
    rows: list[dict[str, Any]] = []
    op_idx = 0
    fp_idx = 0
    for failure in failures:
        row = manifest.get(str(failure.get("row_id")))
        if not row:
            continue
        labels = set(str(x) for x in failure.get("labels", []) if isinstance(x, str))
        if "keeps_the_repetition" in labels or "pator_fragment" in labels:
            new = normalize_operator_route(row, failure, op_idx)
            new["split"] = failure.get("split") or row.get("split") or "train"
            rows.append(new)
            op_idx += 1
        elif "associated_lis" in labels:
            rows.append(file_path_repair(row, failure, fp_idx))
            fp_idx += 1
    split_balance(rows)
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    split_counts: dict[str, int] = {}
    task_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    surface_counts: dict[str, int] = {}
    unsafe_rows: list[str] = []
    for row in rows:
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        task_counts[str(row.get("repair_task_type"))] = task_counts.get(str(row.get("repair_task_type")), 0) + 1
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        route_counts[str(model_input.get("opaque_phrase_route_id"))] = route_counts.get(str(model_input.get("opaque_phrase_route_id")), 0) + 1
        surface_counts[str(model_input.get("semantic_surface_kind"))] = surface_counts.get(str(model_input.get("semantic_surface_kind")), 0) + 1
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if loss.get("decoder_ce") or loss.get("structured_aux") or loss.get("runtime_reward") or not loss.get("denoise_ce"):
            unsafe_rows.append(str(row.get("row_id")))
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(str(row.get("row_id")))
    if source.get("stage") != 9339 or source.get("passed") is not False:
        failures.append("source_stage9339_not_failed_quality_audit")
    if len(rows) != 18:
        failures.append("unexpected_row_count")
    if not {"operator_route_separated_repair", "repair_file_path_associated_with"}.issubset(task_counts):
        failures.append("missing_required_repair_tasks")
    if route_counts.get("route_1", 0) < 16 or route_counts.get("route_file_path", 0) != 2:
        failures.append("unexpected_route_counts")
    if surface_counts.get("edit_action_argument", 0) < 16 or surface_counts.get("file_path_argument", 0) != 2:
        failures.append("unexpected_surface_counts")
    if set(split_counts) != {"train", "eval", "strict_eval"}:
        failures.append("missing_split_coverage")
    if unsafe_rows:
        failures.append("unsafe_rows")
    return {"passed": not failures, "failures": failures, "rows": len(rows), "split_counts": split_counts, "task_counts": task_counts, "route_counts": route_counts, "surface_counts": surface_counts, "unsafe_rows": unsafe_rows[:20], "manifest_sha256": sha_file(MANIFEST), "authority": dict(AUTHORITY_CLOSED)}


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
    OUT_DIR.mkdir(parents=True, exist_ok=True); SUMMARY.parent.mkdir(parents=True, exist_ok=True); DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows(); write_jsonl(MANIFEST, rows)
    audit = audit_rows(rows); audit["manifest_sha256"] = sha_file(MANIFEST)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Built route-separated operator and file-path repair rows from Stage9339 residuals; decoder CE remains closed.", "next_best_step": "Build Stage9341 preexecution for a tiny operator-route separation repair probe.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9340 Operator Route Separation Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{audit['split_counts']}`", f"Tasks: `{audit['task_counts']}`", f"Routes: `{audit['route_counts']}`", f"Surfaces: `{audit['surface_counts']}`", "These rows repair Stage9339 operator/dependency route interference and file-path `associated lis` failures.", "Decoder CE, runtime, Gemma, harness, source/body emission, scoring, and promotion remain closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": audit["rows"], "split_counts": audit["split_counts"], "task_counts": audit["task_counts"], "route_counts": audit["route_counts"], "failures": audit["failures"]}}, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
