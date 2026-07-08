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
STAGE = 9352
NAME = "stage9352_full_mixture_with_schema_and_terminal_repairs_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9351_operator_terminal_probe_audit.json"
BASE = ROOT / "runs/local/artifacts/stage9343_full_mixture_with_operator_route_repairs_manifest/full_mixture_with_operator_route_repairs_manifest.jsonl"
BRIDGE = ROOT / "runs/local/artifacts/stage9346_schema_normalized_subword_bridge_repair_manifest/schema_normalized_subword_bridge_repair_manifest.jsonl"
TERMINAL = ROOT / "runs/local/artifacts/stage9349_operator_terminal_anti_repetition_manifest/operator_terminal_anti_repetition_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "full_mixture_with_schema_and_terminal_repairs_manifest.jsonl"
AUDIT = OUT_DIR / "full_mixture_with_schema_and_terminal_repairs_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_MIXTURE_WITH_SCHEMA_AND_TERMINAL_REPAIRS_MANIFEST_STAGE9352.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED_FEATURES = ["semantic_surface_kind", "semantic_affordance", "opaque_phrase_route_id", "anchor_object_kind"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def target_text(row: dict[str, Any]) -> str:
    return str(row.get("clean_target") or row.get("target_text") or row.get("target", {}).get("text") if isinstance(row.get("target"), dict) else row.get("clean_target") or "")


def infer_schema(row: dict[str, Any]) -> dict[str, str]:
    target = str(row.get("clean_target") or "")
    lower = target.lower()
    if "dependency handle" in lower:
        return {
            "semantic_surface_kind": "dependency_handle",
            "semantic_affordance": "contain_change_scope",
            "opaque_phrase_route_id": "route_0",
            "anchor_object_kind": "dependency_handle",
        }
    if "callable endpoint" in lower:
        return {
            "semantic_surface_kind": "edit_action_argument",
            "semantic_affordance": "choose_edit_action",
            "opaque_phrase_route_id": "route_1",
            "anchor_object_kind": "callable_endpoint",
        }
    if "file path associated" in lower:
        return {
            "semantic_surface_kind": "file_path_argument",
            "semantic_affordance": "select_edit_location_path",
            "opaque_phrase_route_id": "route_file_path",
            "anchor_object_kind": "file_path",
        }
    if "small constant" in lower:
        return {
            "semantic_surface_kind": "numeric_argument",
            "semantic_affordance": "keep_expected_relation",
            "opaque_phrase_route_id": "route_2",
            "anchor_object_kind": "small_constant",
        }
    mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    return {
        "semantic_surface_kind": str(mi.get("semantic_surface_kind") or "bounded_argument"),
        "semantic_affordance": str(mi.get("semantic_affordance") or "repair_bounded_argument"),
        "opaque_phrase_route_id": str(mi.get("opaque_phrase_route_id") or "route_bridge"),
        "anchor_object_kind": str(mi.get("anchor_object_kind") or "bounded_argument"),
    }


def remap(source_name: str, source_stage: int, row: dict[str, Any]) -> dict[str, Any]:
    new = copy.deepcopy(row)
    old_id = str(row.get("row_id"))
    new["row_id"] = f"stage9352_{source_name}_{old_id}"
    new["source_row_id"] = old_id
    new["source_stage"] = source_stage
    new["merged_curriculum_source"] = source_name
    new["objective_family"] = "full_mixture_with_schema_and_terminal_repairs_denoise"
    new["authority"] = dict(AUTHORITY_CLOSED)
    new["loss_mask"] = {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}
    schema = infer_schema(new)
    mi = new.get("model_input") if isinstance(new.get("model_input"), dict) else {}
    mi.update(schema)
    mi.update(
        {
            "merged_curriculum_source": source_name,
            "schema_normalized_rejoin_probe": True,
            "route_schema_version": "stage9352_full_mixture_schema_v1",
            "clean_target_hidden_from_model_input": True,
            "remaining_suffix_hidden_from_model_input": True,
            "first_suffix_word_hidden_from_model_input": True,
        }
    )
    for forbidden_key in ["clean_target", "target_text", "target_phrase", "remaining_suffix", "first_suffix_word"]:
        mi.pop(forbidden_key, None)
    new["model_input"] = mi
    state = new.get("input_state") if isinstance(new.get("input_state"), dict) else {}
    state.update(
        {
            "target_text_sha256": hashlib.sha256(str(new.get("clean_target") or "").encode("utf-8")).hexdigest(),
            "target_remainder_hidden": True,
            "target_suffix_hidden": True,
            "remaining_suffix_hidden_from_model_input": True,
            "decode_allowed": False,
            "repair_required": True,
        }
    )
    new["input_state"] = state
    anti = new.get("anti_cheat") if isinstance(new.get("anti_cheat"), dict) else {}
    anti.update(
        {
            "decoder_ce_closed": True,
            "runtime_closed": True,
            "schema_normalized_rejoin_probe": True,
            "clean_target_in_model_input": False,
            "remaining_suffix_visible": False,
        }
    )
    new["anti_cheat"] = anti
    return new


def build_rows() -> list[dict[str, Any]]:
    return (
        [remap("base_schema_normalized", 9343, row) for row in load_jsonl(BASE)]
        + [remap("schema_bridge_repair", 9346, row) for row in load_jsonl(BRIDGE)]
        + [remap("operator_terminal_repair", 9349, row) for row in load_jsonl(TERMINAL)]
    )


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    split_counts = Counter(str(row.get("split")) for row in rows)
    source_counts = Counter(str(row.get("merged_curriculum_source")) for row in rows)
    task_counts = Counter(str(row.get("repair_task_type")) for row in rows)
    route_counts = Counter(str(row.get("model_input", {}).get("opaque_phrase_route_id")) for row in rows)
    surface_counts = Counter(str(row.get("model_input", {}).get("semantic_surface_kind")) for row in rows)
    missing_features: list[str] = []
    unsafe_rows: list[str] = []
    target_visible_rows: list[str] = []
    row_ids: set[str] = set()
    duplicate_rows: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        if row_id in row_ids:
            duplicate_rows.append(row_id)
        row_ids.add(row_id)
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if any(not mi.get(feature) for feature in REQUIRED_FEATURES):
            missing_features.append(row_id)
        if loss != {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}:
            unsafe_rows.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row_id)
        target = str(row.get("clean_target") or "")
        if target and target in json.dumps(mi, sort_keys=True):
            target_visible_rows.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9351_not_passed")
    if len(rows) != 122:
        failures.append("unexpected_row_count")
    if dict(split_counts) != {"train": 65, "eval": 36, "strict_eval": 21}:
        failures.append("unexpected_split_counts")
    if dict(source_counts) != {"base_schema_normalized": 74, "schema_bridge_repair": 31, "operator_terminal_repair": 17}:
        failures.append("unexpected_source_counts")
    if missing_features:
        failures.append("missing_required_features")
    if unsafe_rows:
        failures.append("unsafe_rows")
    if target_visible_rows:
        failures.append("target_visible_in_model_input")
    if duplicate_rows:
        failures.append("duplicate_row_ids")
    if route_counts.get("route_1", 0) < 50 or route_counts.get("route_0", 0) < 20 or route_counts.get("route_file_path", 0) < 4:
        failures.append("insufficient_core_route_coverage")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "task_counts": dict(sorted(task_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "surface_counts": dict(sorted(surface_counts.items())),
        "missing_feature_rows": missing_features[:20],
        "unsafe_rows": sorted(set(unsafe_rows))[:20],
        "target_visible_rows": target_visible_rows[:20],
        "duplicate_rows": duplicate_rows[:20],
        "manifest_sha256": sha(MANIFEST),
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
    audit["manifest_sha256"] = sha(MANIFEST)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Merged the full mixture with schema-normalized bridge repairs and operator-terminal anti-repetition repairs.",
        "next_best_step": "Build Stage9353 preexecution and run a 122-row closed full-mixture rejoin probe before any decoder CE step.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9352 Full Mixture With Schema And Terminal Repairs Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{audit['split_counts']}`",
                f"Sources: `{audit['source_counts']}`",
                f"Routes: `{audit['route_counts']}`",
                f"Surfaces: `{audit['surface_counts']}`",
                "",
                "The original full mixture is schema-normalized before rejoining the Stage9346 and Stage9349 repair rows. Decoder CE, runtime, harness, Gemma, scoring, promotion, and checkpoint export remain closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "split_counts", "source_counts", "route_counts", "surface_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
