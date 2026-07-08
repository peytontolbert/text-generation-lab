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
STAGE = 9334
NAME = "stage9334_targeted_anti_insertion_repetition_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9333_routed_ladder_suffix_probe_audit.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9333_routed_ladder_suffix_probe/stage9333_routed_ladder_suffix_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9331_routed_ladder_suffix_manifest/routed_ladder_suffix_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "targeted_anti_insertion_repetition_manifest.jsonl"
AUDIT = OUT_DIR / "targeted_anti_insertion_repetition_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGETED_ANTI_INSERTION_REPETITION_MANIFEST_STAGE9334.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ERROR_TO_TASK = {
    "keeps_the_repetition": "repair_repeated_keeps_the",
    "verified_inserted_before_preserves": "remove_wrong_verified_before_preserves",
    "extra_verified_before_preserves": "remove_wrong_verified_before_preserves",
    "operatch_repetition": "repair_operatch_repetition",
    "boundary_whitespace_over_expected": "repair_boundary_whitespace_choice",
}


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


def split_for(index: int, source_split: str | None) -> str:
    if source_split in {"train", "eval", "strict_eval"}:
        return source_split
    return ["train", "eval", "strict_eval"][index % 3]


def primary_task(labels: list[str]) -> str:
    for label in labels:
        if label in ERROR_TO_TASK and label != "boundary_whitespace_over_expected":
            return ERROR_TO_TASK[label]
    for label in labels:
        if label in ERROR_TO_TASK:
            return ERROR_TO_TASK[label]
    return "repair_other_suffix_error"


def build_rows() -> list[dict[str, Any]]:
    source_audit = load_json(SOURCE_AUDIT)
    source_rows = {str(row.get("row_id")): row for row in load_jsonl(SOURCE_MANIFEST)}
    failures = source_audit.get("failed_samples") if isinstance(source_audit.get("failed_samples"), list) else []
    rows: list[dict[str, Any]] = []
    for idx, failure in enumerate(failures):
        source_row_id = str(failure.get("row_id"))
        base = source_rows.get(source_row_id, {})
        model_input = base.get("model_input") if isinstance(base.get("model_input"), dict) else {}
        labels = [str(x) for x in failure.get("labels", []) if isinstance(x, str)]
        task = primary_task(labels)
        target = str(failure.get("target") or base.get("clean_target") or (base.get("target") or {}).get("decoder_text") or "")
        generated = str(failure.get("generated") or "")
        prefix = str(model_input.get("active_generation_prefix_span") or failure.get("target", "").split(" ")[0])
        route_id = str(model_input.get("opaque_phrase_route_id") or failure.get("route") or "route_unknown")
        phrase_id = failure.get("phrase_id") or (base.get("target") if isinstance(base.get("target"), dict) else {}).get("phrase_id")
        error_signature = "+".join(labels) if labels else "unknown_error"
        new_model_input = {
            "active_generation_prefix_span": prefix,
            "active_generation_prefix_words": model_input.get("active_generation_prefix_words") or failure.get("prefix_words"),
            "bad_output_text": generated,
            "bad_output_sha256": sha_text(generated),
            "clean_target_sha256": sha_text(target),
            "decoder_repair_mode": "targeted_bad_output_to_clean_output",
            "error_signature": error_signature,
            "forbidden_error_patterns": labels,
            "opaque_phrase_route_id": route_id,
            "phrase_id": phrase_id or "none",
            "remaining_suffix_hidden_from_model_input": True,
            "route_conditioned": bool(model_input.get("route_conditioned")),
            "routed_ladder_source": base.get("combined_curriculum_source") or failure.get("source"),
            "semantic_surface_kind": model_input.get("semantic_surface_kind") or model_input.get("anchor_object_kind") or "bounded_argument_repair",
            "target_grounding_mode": "targeted_anti_insertion_repetition_repair_v1",
            "target_text_hidden_except_hash": True,
        }
        input_state = {
            "authority_closed": True,
            "decode_allowed": False,
            "decoder_budget_ok": True,
            "error_labels": labels,
            "repair_required": True,
            "target_shape": "bounded_decoder_argument",
        }
        rows.append({
            "row_id": f"stage9334_{idx:03d}_{task}_{sha_text(source_row_id + generated)}",
            "source_stage": 9333,
            "source_row_id": source_row_id,
            "source_split": failure.get("split"),
            "split": split_for(idx, failure.get("split") if isinstance(failure.get("split"), str) else None),
            "objective_family": "targeted_anti_insertion_repetition_denoise",
            "repair_task_type": task,
            "route": "USE_FOR_DENOISE_REPAIR",
            "language_family": base.get("language_family") or "mixed",
            "combined_curriculum_source": base.get("combined_curriculum_source") or failure.get("source"),
            "corrupted_output": generated,
            "clean_target": target,
            "input_state": input_state,
            "model_input": new_model_input,
            "target": {"decoder_text": target, "phrase_id": phrase_id or "none"},
            "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
            "authority": dict(AUTHORITY_CLOSED),
            "anti_cheat": {
                "decoder_ce_closed": True,
                "runtime_closed": True,
                "source_body_absent": True,
                "target_text_hidden_except_hash": True,
                "bad_output_visible_for_repair_objective": True,
                "repair_manifest_not_decoder_readiness_claim": True,
            },
        })
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    split_counts: dict[str, int] = {}
    task_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    phrase_counts: dict[str, int] = {}
    unsafe_rows: list[str] = []
    for row in rows:
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        task_counts[str(row.get("repair_task_type"))] = task_counts.get(str(row.get("repair_task_type")), 0) + 1
        source_counts[str(row.get("combined_curriculum_source"))] = source_counts.get(str(row.get("combined_curriculum_source")), 0) + 1
        phrase = (row.get("target") if isinstance(row.get("target"), dict) else {}).get("phrase_id")
        phrase_counts[str(phrase)] = phrase_counts.get(str(phrase), 0) + 1
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if loss.get("decoder_ce") or loss.get("structured_aux") or loss.get("runtime_reward") or not loss.get("denoise_ce"):
            unsafe_rows.append(str(row.get("row_id")))
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(str(row.get("row_id")))
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        target = (row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text")
        if isinstance(target, str) and model_input.get("clean_target_sha256") != sha_text(target):
            unsafe_rows.append(str(row.get("row_id")))
    if source_summary.get("stage") != 9333 or source_summary.get("passed") is not False:
        failures.append("source_stage9333_not_failed_quality_audit")
    if len(rows) < 20:
        failures.append("too_few_targeted_rows")
    required_tasks = {"repair_repeated_keeps_the", "remove_wrong_verified_before_preserves", "repair_operatch_repetition"}
    if not required_tasks.issubset(task_counts):
        failures.append("missing_required_repair_tasks")
    if set(split_counts) != {"train", "eval", "strict_eval"}:
        failures.append("missing_split_coverage")
    if unsafe_rows:
        failures.append("unsafe_rows")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "task_counts": task_counts,
        "source_counts": source_counts,
        "phrase_counts": phrase_counts,
        "unsafe_rows": unsafe_rows[:20],
        "manifest_sha256": sha_file(MANIFEST),
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
    audit["manifest_sha256"] = sha_file(MANIFEST)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built targeted denoising rows from Stage9333 residual generated-output failures; decoder CE remains closed.",
        "next_best_step": "Build Stage9335 preexecution for a tiny targeted anti-insertion/repetition repair probe before reconnecting the full routed ladder.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9334 Targeted Anti-Insertion/Repetition Manifest",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Splits: `{audit['split_counts']}`",
        f"Repair tasks: `{audit['task_counts']}`",
        f"Sources: `{audit['source_counts']}`",
        "These rows are generated from Stage9333 failures and train bad-output repair, not open-ended decoder readiness.",
        "Decoder CE, runtime, Gemma, harness, source/body emission, scoring, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": audit["rows"], "split_counts": audit["split_counts"], "task_counts": audit["task_counts"], "failures": audit["failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
