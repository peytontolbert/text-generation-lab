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
STAGE = 9328
NAME = "stage9328_phrase_router_mixture_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9327_phrase_router_mixture_design.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9319_phrase_completion_balance_manifest/phrase_completion_balance_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "phrase_router_mixture_manifest.jsonl"
AUDIT = OUT_DIR / "phrase_router_mixture_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHRASE_ROUTER_MIXTURE_MANIFEST_STAGE9328.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ROUTE_META = {
    "phrase_a": {"route_id": "route_0", "semantic_surface_kind": "dependency_handle", "anchor_object_kind": "dependency_handle", "semantic_affordance": "contain_change_scope", "language_family": "web_js_ts_html"},
    "phrase_b": {"route_id": "route_1", "semantic_surface_kind": "edit_action_argument", "anchor_object_kind": "callable_endpoint", "semantic_affordance": "choose_edit_action", "language_family": "cpp"},
    "phrase_c": {"route_id": "route_2", "semantic_surface_kind": "numeric_argument", "anchor_object_kind": "small_constant", "semantic_affordance": "keep_expected_relation", "language_family": "python"},
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def route_row(row: dict[str, Any]) -> dict[str, Any]:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    phrase_id = str(target.get("phrase_id"))
    meta = ROUTE_META[phrase_id]
    new = json.loads(json.dumps(row))
    new["row_id"] = f"stage9328_router_{phrase_id}_{row['row_id']}"
    new["source_stage"] = 9319
    new["source_row_id"] = row["row_id"]
    new["objective_family"] = "phrase_router_conditioned_denoise"
    new["language_family"] = meta["language_family"]
    new["authority"] = dict(AUTHORITY_CLOSED)
    new["loss_mask"] = {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}

    input_state = new.get("input_state") if isinstance(new.get("input_state"), dict) else {}
    input_state.update({
        "opaque_phrase_route_id": meta["route_id"],
        "semantic_surface_kind": meta["semantic_surface_kind"],
        "anchor_object_kind": meta["anchor_object_kind"],
        "semantic_affordance": meta["semantic_affordance"],
        "target_shape": "bounded_decoder_argument",
        "decoder_budget_ok": True,
    })
    new["input_state"] = input_state

    model_input = new.get("model_input") if isinstance(new.get("model_input"), dict) else {}
    model_input.update({
        "opaque_phrase_route_id": meta["route_id"],
        "semantic_surface_kind": meta["semantic_surface_kind"],
        "anchor_object_kind": meta["anchor_object_kind"],
        "semantic_affordance": meta["semantic_affordance"],
        "route_conditioned": True,
        "target_grounding_mode": f"route_conditioned_{model_input.get('target_grounding_mode', 'unknown')}",
        "external_phrase_label_hidden": True,
    })
    new["model_input"] = model_input

    anti_cheat = new.get("anti_cheat") if isinstance(new.get("anti_cheat"), dict) else {}
    anti_cheat.update({
        "route_id_is_opaque": True,
        "semantic_discriminators_are_nonlabel": True,
        "literal_target_suffix_hidden": True,
        "decoder_ce_closed": True,
    })
    new["anti_cheat"] = anti_cheat
    return new


def build_rows() -> list[dict[str, Any]]:
    rows = [route_row(row) for row in load_jsonl(SOURCE_MANIFEST)]
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    split_counts: dict[str, int] = {}
    phrase_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    variant_counts: dict[str, int] = {}
    unsafe_rows: list[str] = []
    suffix_visible_rows: list[str] = []
    for row in rows:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        phrase_id = str(target.get("phrase_id"))
        phrase_counts[phrase_id] = phrase_counts.get(phrase_id, 0) + 1
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        route_counts[str(model_input.get("opaque_phrase_route_id"))] = route_counts.get(str(model_input.get("opaque_phrase_route_id")), 0) + 1
        variant_counts[row["repair_task_type"]] = variant_counts.get(row["repair_task_type"], 0) + 1
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if loss_mask.get("decoder_ce") or loss_mask.get("structured_aux") or not loss_mask.get("denoise_ce"):
            unsafe_rows.append(row["row_id"])
        if any(bool(authority.get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row["row_id"])
        target_text = str(target.get("decoder_text") or "")
        prefix = model_input.get("active_generation_prefix_span")
        visible = json.dumps(model_input, sort_keys=True)
        if row["repair_task_type"] == "clean_prefix_to_phrase_completion" and isinstance(prefix, str) and target_text.startswith(prefix):
            suffix = target_text[len(prefix):].strip()
            if suffix and suffix in visible:
                suffix_visible_rows.append(row["row_id"])
    if source.get("passed") is not True:
        failures.append("source_stage9327_not_passed")
    if len(rows) != 24:
        failures.append("unexpected_row_count")
    if split_counts != {"train": 8, "eval": 8, "strict_eval": 8}:
        failures.append("unexpected_split_counts")
    if phrase_counts != {"phrase_a": 8, "phrase_b": 8, "phrase_c": 8}:
        failures.append("unexpected_phrase_counts")
    if route_counts != {"route_0": 8, "route_1": 8, "route_2": 8}:
        failures.append("unexpected_route_counts")
    if unsafe_rows:
        failures.append("unsafe_rows")
    if suffix_visible_rows:
        failures.append("suffix_visible_rows")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "phrase_counts": phrase_counts,
        "route_counts": route_counts,
        "variant_counts": variant_counts,
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
        "decision": "Built a route-conditioned phrase mixture manifest with opaque route IDs and non-label semantic discriminators.",
        "next_best_step": "Build Stage9329 preexecution and run the tiny target-100M route-conditioned phrase mixture probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9328 Phrase Router Mixture Manifest",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Phrase counts: `{audit['phrase_counts']}`",
        f"Route counts: `{audit['route_counts']}`",
        "The manifest adds opaque phrase route IDs and non-label semantic discriminators before recombining phrase families.",
        "Decoder CE, runtime, Gemma, harness, source/body emission, scoring, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": audit["rows"], "phrase_counts": audit["phrase_counts"], "route_counts": audit["route_counts"], "failures": audit["failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
