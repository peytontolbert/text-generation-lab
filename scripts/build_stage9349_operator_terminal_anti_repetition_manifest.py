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
STAGE = 9349
NAME = "stage9349_operator_terminal_anti_repetition_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9348_schema_normalized_bridge_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9346_schema_normalized_subword_bridge_repair_manifest/schema_normalized_subword_bridge_repair_manifest.jsonl"
SOURCE_RUN = ROOT / "runs/local/artifacts/stage9348_schema_normalized_bridge_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "operator_terminal_anti_repetition_manifest.jsonl"
AUDIT = OUT_DIR / "operator_terminal_anti_repetition_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_TERMINAL_ANTI_REPETITION_MANIFEST_STAGE9349.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def failed_operator_samples() -> list[dict[str, Any]]:
    card = load_json(SOURCE_RUN / "sample_generation_audit.json")
    samples = card.get("samples") if isinstance(card.get("samples"), list) else []
    return [
        sample
        for sample in samples
        if not sample.get("exact_match")
        and "operatch" in str(sample.get("generated_text") or "")
        and "patch operator" in str(sample.get("target_text") or "")
    ]


def build_rows() -> list[dict[str, Any]]:
    source_rows = {str(row.get("row_id")): row for row in load_jsonl(SOURCE_MANIFEST)}
    rows: list[dict[str, Any]] = []
    for idx, sample in enumerate(failed_operator_samples()):
        source_id = str(sample.get("row_id"))
        source = source_rows[source_id]
        row = copy.deepcopy(source)
        target = str(sample.get("target_text") or source.get("clean_target") or "")
        generated = str(sample.get("generated_text") or "")
        prefix = str(sample.get("generation_prefix_text") or "")
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        input_state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        row_id = f"stage9349_operator_terminal_{idx:03d}_{short_hash(source_id + generated)}"
        model_input.update(
            {
                "active_generation_prefix_span": prefix,
                "active_generation_prefix_words": len(prefix.split()),
                "anchor_object_kind": "callable_endpoint",
                "bridge_error_family": "operator_terminal_operatch_repetition",
                "bridge_repair_objective": "operator_terminal_anti_repetition",
                "clean_target_hidden_from_model_input": True,
                "corrupted_output_fragment": "operatch",
                "forbidden_repetition_fragment": "operatch",
                "max_terminal_phrase_repetitions": 1,
                "opaque_phrase_route_id": "route_1",
                "remaining_suffix_hidden_from_model_input": True,
                "route_schema_version": "stage9349_operator_terminal_v1",
                "semantic_affordance": "choose_edit_action",
                "semantic_surface_kind": "edit_action_argument",
                "stop_after_terminal_argument": True,
            }
        )
        for forbidden_key in ["clean_target", "target_text", "target_phrase", "remaining_suffix", "first_suffix_word"]:
            model_input.pop(forbidden_key, None)
        input_state.update(
            {
                "source_stage9348_row_id": source_id,
                "source_stage9348_generated_sha256": hashlib.sha256(generated.encode("utf-8")).hexdigest(),
                "target_text_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
                "decode_allowed": False,
                "repair_required": True,
                "terminal_repetition_repair_required": True,
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
                "operator_terminal_anti_repetition": True,
            }
        )
        row.update(
            {
                "row_id": row_id,
                "source_stage": STAGE,
                "source_stage9348_row_id": source_id,
                "split": sample.get("split") or source.get("split"),
                "merged_curriculum_source": "operator_terminal_anti_repetition",
                "combined_curriculum_source": "operator_terminal_repair",
                "repair_task_type": "operator_terminal_operatch_repetition",
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
    route_counts = Counter(str(row.get("model_input", {}).get("opaque_phrase_route_id")) for row in rows)
    unsafe_rows: list[str] = []
    target_visible_rows: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if loss != {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}:
            unsafe_rows.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row_id)
        if mi.get("opaque_phrase_route_id") != "route_1" or mi.get("semantic_surface_kind") != "edit_action_argument":
            unsafe_rows.append(row_id)
        target = str(row.get("clean_target") or "")
        if target and target in json.dumps(mi, sort_keys=True):
            target_visible_rows.append(row_id)
    failures: list[str] = []
    if len(rows) != 17:
        failures.append("unexpected_row_count")
    if split_counts != {"train": 8, "eval": 7, "strict_eval": 2}:
        failures.append("unexpected_split_counts")
    if route_counts != {"route_1": 17}:
        failures.append("unexpected_route_counts")
    if unsafe_rows:
        failures.append("unsafe_rows")
    if target_visible_rows:
        failures.append("target_visible_in_model_input")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
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
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    if source.get("passed") is not False or metrics.get("safety_gate_passed") is not True:
        audit["passed"] = False
        audit.setdefault("failures", []).append("source_stage9348_not_safe_failed_audit")
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
        "decision": "Built denoise-only route_1 rows for the Stage9348 `operatch` terminal repetition failure.",
        "next_best_step": "Build Stage9350 preexecution for a 17-row operator-terminal anti-repetition probe; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9349 Operator Terminal Anti-Repetition Manifest",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{audit['split_counts']}`",
                f"Routes: `{audit['route_counts']}`",
                "",
                "This manifest isolates the Stage9348 route_1 failure: `patch operatch ... operator`. It keeps the solved dependency and file-path bridge rows out of the repair set and trains only denoise CE.",
                "",
                "Decoder CE, runtime, harness, Gemma, scoring, source/body emission, checkpoint export, controller merge, and promotion remain closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "split_counts", "route_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
