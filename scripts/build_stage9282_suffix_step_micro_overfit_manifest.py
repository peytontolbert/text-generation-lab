#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9282
NAME = "stage9282_suffix_step_micro_overfit_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9281_suffix_boundary_token_loss_diagnostic.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9279_bridge_primed_denoise_manifest/bridge_primed_denoise_manifest.jsonl"
BOUNDARY_ROWS = ROOT / "runs/local/artifacts/stage9281_suffix_boundary_token_loss_diagnostic/suffix_boundary_rows.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "suffix_step_micro_overfit_manifest.jsonl"
AUDIT = OUT_DIR / "suffix_step_micro_overfit_manifest_audit.json"
CARD = OUT_DIR / "suffix_step_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_STEP_MICRO_OVERFIT_MANIFEST_STAGE9282.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUTHORITY_FALSE = dict(AUTHORITY_CLOSED)
MAX_SOURCE_ROWS = 8
MAX_SUFFIX_WORDS = 8
MAX_PARTIAL_TARGET_CHARS = 160
FORBIDDEN_TOP_LEVEL = {"source_text", "body", "raw_body", "patch_body", "hidden_eval", "locked_eval", "runtime_output", "gemma_output"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text)


def suffix_step_target(full_target: str, priming: str) -> tuple[str, str]:
    if not full_target.startswith(priming):
        return "", ""
    remainder = full_target[len(priming):]
    matches = list(re.finditer(r"[A-Za-z][A-Za-z0-9_-]*", remainder))
    if not matches:
        return "", ""
    end = matches[min(MAX_SUFFIX_WORDS, len(matches)) - 1].end()
    suffix = remainder[:end].rstrip()
    partial = (priming + suffix).strip()
    if len(partial) > MAX_PARTIAL_TARGET_CHARS:
        partial = partial[:MAX_PARTIAL_TARGET_CHARS].rstrip()
        if not partial.startswith(priming):
            return "", ""
        suffix = partial[len(priming):]
    return partial, suffix.strip()


def source_lookup() -> dict[str, dict[str, Any]]:
    return {str(row.get("row_id")): row for row in load_jsonl(SOURCE_MANIFEST)}


def selected_boundary_rows() -> list[dict[str, Any]]:
    rows = [row for row in load_jsonl(BOUNDARY_ROWS) if row.get("first_unforced_loss") is not None]
    rows = sorted(rows, key=lambda row: float(row.get("first_unforced_loss") or -1), reverse=True)
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        row_id = str(row.get("row_id"))
        if row_id in seen:
            continue
        seen.add(row_id)
        unique.append(row)
        if len(unique) >= MAX_SOURCE_ROWS:
            break
    return unique


def visible_projection(row: dict[str, Any]) -> str:
    payload = {
        "row_id": row.get("row_id"),
        "source_row_id": row.get("source_row_id"),
        "split": row.get("split"),
        "language_family": row.get("language_family"),
        "route": row.get("route"),
        "objective_family": row.get("objective_family"),
        "repair_task_type": row.get("repair_task_type"),
        "corrupted_output": row.get("corrupted_output"),
        "input_state": row.get("input_state"),
        "model_input": row.get("model_input"),
        "loss_mask": row.get("loss_mask"),
    }
    return json.dumps(payload, sort_keys=True)


def build_rows() -> list[dict[str, Any]]:
    source_rows = source_lookup()
    rows: list[dict[str, Any]] = []
    split_cycle = ["train", "train", "train", "train", "eval", "strict_eval", "train", "strict_eval"]
    for idx, boundary in enumerate(selected_boundary_rows()):
        source = source_rows.get(str(boundary.get("row_id")))
        if not source:
            continue
        full_target = str((source.get("target") or {}).get("decoder_text") or source.get("clean_target") or "")
        priming = str(boundary.get("priming_span") or (source.get("model_input") or {}).get("bridge_priming_span") or "")
        partial_target, suffix_span = suffix_step_target(full_target, priming)
        row = dict(source)
        row["row_id"] = f"stage9282_suffixstep_{idx:03d}_{sha(str(boundary.get('row_id')))[:12]}"
        row["source_stage"] = STAGE
        row["source_manifest_stage"] = 9279
        row["source_boundary_stage"] = 9281
        row["source_repair_row_id"] = source.get("row_id")
        row["diagnostic_source_split"] = boundary.get("split")
        row["split"] = split_cycle[idx % len(split_cycle)]
        row["objective_family"] = "suffix_step_micro_overfit_denoise_repair"
        row["repair_task_type"] = "suffix_step_after_bridge_priming_to_partial_clean_target"
        row["target"] = {"decoder_text": partial_target}
        row["clean_target"] = partial_target
        state = dict(source.get("input_state") if isinstance(source.get("input_state"), dict) else {})
        state.update({
            "suffix_step_micro_overfit": True,
            "bridge_priming_span": priming,
            "suffix_step_hidden_from_model_input": True,
            "suffix_step_word_count": len(words(suffix_span)),
            "suffix_step_char_count": len(suffix_span),
            "partial_target_char_count": len(partial_target),
            "full_target_sha256": sha(full_target),
            "partial_target_sha256": sha(partial_target),
            "source_first_unforced_loss": boundary.get("first_unforced_loss"),
            "source_suffix_mean_loss": boundary.get("suffix_mean_loss"),
            "source_boundary_position": boundary.get("boundary_position"),
            "full_target_remainder_hidden": True,
        })
        row["input_state"] = state
        model_input = dict(source.get("model_input") if isinstance(source.get("model_input"), dict) else {})
        model_input.update({
            "target_grounding_mode": "suffix_step_micro_overfit_v1",
            "bridge_priming_span": priming,
            "bridge_priming_then_short_suffix": True,
            "suffix_step_word_count": len(words(suffix_span)),
            "full_target_remainder_hidden": True,
        })
        model_input.pop("continuation_bridge_span", None)
        row["model_input"] = model_input
        row["anti_cheat"] = {
            "full_original_target_in_model_visible_fields": False,
            "partial_target_in_model_visible_fields": False,
            "suffix_step_in_model_visible_fields": False,
            "bridge_priming_visible": True,
            "full_target_remainder_hidden": True,
            "max_suffix_words": MAX_SUFFIX_WORDS,
            "max_partial_target_chars": MAX_PARTIAL_TARGET_CHARS,
            "decoder_ce_closed": True,
            "runtime_closed": True,
        }
        row["loss_mask"] = {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False}
        row["authority"] = AUTHORITY_FALSE
        rows.append(row)
    return rows


def audit_rows(rows: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("source_stage9281_not_passed")
    if not rows:
        failures.append("manifest_empty")
    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    priming_visible_rows = 0
    partial_target_visible_rows = 0
    suffix_visible_rows = 0
    full_original_target_visible_rows = 0
    invalid_suffix_rows = 0
    over_cap_rows = 0
    authority_rows = 0
    unsafe_loss_rows = 0
    forbidden_key_rows = 0
    cards: list[dict[str, Any]] = []
    for row in rows:
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        language_counts[str(row.get("language_family"))] = language_counts.get(str(row.get("language_family")), 0) + 1
        target = str((row.get("target") or {}).get("decoder_text") or "")
        full_hash = str((row.get("input_state") or {}).get("full_target_sha256") or "")
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        priming = str(model_input.get("bridge_priming_span") or "")
        suffix = target[len(priming):].strip() if target.startswith(priming) else ""
        visible = visible_projection(row)
        if priming and priming in visible:
            priming_visible_rows += 1
        if target and target in visible:
            partial_target_visible_rows += 1
        if suffix and len(suffix) > 8 and suffix in visible:
            suffix_visible_rows += 1
        if full_hash and full_hash in visible and "full_target_sha256" not in visible:
            full_original_target_visible_rows += 1
        if not priming or not target.startswith(priming) or not suffix:
            invalid_suffix_rows += 1
        if len(words(suffix)) > MAX_SUFFIX_WORDS or len(target) > MAX_PARTIAL_TARGET_CHARS:
            over_cap_rows += 1
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        if mask.get("denoise_ce") is not True or mask.get("decoder_ce") is not False or mask.get("runtime_reward") is not False:
            unsafe_loss_rows += 1
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else row
        if any(bool(auth.get(key, False)) for key in AUTHORITY_CLOSED):
            authority_rows += 1
        if set(row).intersection(FORBIDDEN_TOP_LEVEL):
            forbidden_key_rows += 1
        cards.append({
            "row_id": row.get("row_id"),
            "split": row.get("split"),
            "diagnostic_source_split": row.get("diagnostic_source_split"),
            "language_family": row.get("language_family"),
            "bridge_priming_span": priming,
            "suffix_word_count": len(words(suffix)),
            "partial_target_char_count": len(target),
            "source_first_unforced_loss": (row.get("input_state") or {}).get("source_first_unforced_loss"),
            "partial_target_sha256": sha(target),
        })
    if priming_visible_rows != len(rows):
        failures.append("priming_not_visible_for_all_rows")
    if partial_target_visible_rows:
        failures.append("partial_target_visible_rows_nonzero")
    if suffix_visible_rows:
        failures.append("suffix_visible_rows_nonzero")
    if full_original_target_visible_rows:
        failures.append("full_original_target_visible_rows_nonzero")
    if invalid_suffix_rows:
        failures.append("invalid_suffix_rows_nonzero")
    if over_cap_rows:
        failures.append("over_cap_rows_nonzero")
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows_nonzero")
    if forbidden_key_rows:
        failures.append("forbidden_key_rows_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "source_failure_rows_selected": len(selected_boundary_rows()),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "priming_visible_rows": priming_visible_rows,
        "partial_target_visible_rows": partial_target_visible_rows,
        "suffix_visible_rows": suffix_visible_rows,
        "full_original_target_visible_rows": full_original_target_visible_rows,
        "invalid_suffix_rows": invalid_suffix_rows,
        "over_cap_rows": over_cap_rows,
        "authority_rows": authority_rows,
        "unsafe_loss_rows": unsafe_loss_rows,
        "forbidden_key_rows": forbidden_key_rows,
        "max_suffix_words": MAX_SUFFIX_WORDS,
        "max_partial_target_chars": MAX_PARTIAL_TARGET_CHARS,
        "cards": cards,
        "authority": AUTHORITY_FALSE,
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": AUTHORITY_FALSE, "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    audit = audit_rows(rows, load_json(SOURCE_SUMMARY))
    MANIFEST.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    CARD.write_text(json.dumps(audit["cards"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit_public = {key: value for key, value in audit.items() if key != "cards"}
    AUDIT.write_text(json.dumps(audit_public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_FALSE,
        "metrics": {**AUTHORITY_FALSE, **audit_public},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a suffix-step micro-overfit manifest from the highest first-unforced-loss Stage9281 rows; each target is only bridge priming plus a short immediate suffix.",
        "next_best_step": "Run contract-only preflight for the suffix-step manifest, then a tiny target-100M denoise probe using --generation-prefix-field model_input.bridge_priming_span.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9282 Suffix-Step Micro-Overfit Manifest",
            "",
            "Stage9282 selects the worst first-unforced-loss rows from Stage9281 and shortens each target to bridge priming plus the immediate suffix step.",
            "",
            f"Rows: {audit['rows']}",
            f"Splits: {audit['split_counts']}",
            f"Languages: {audit['language_counts']}",
            f"Partial target visible rows: {audit['partial_target_visible_rows']}",
            f"Suffix visible rows: {audit['suffix_visible_rows']}",
            f"Invalid suffix rows: {audit['invalid_suffix_rows']}",
            f"Over-cap rows: {audit['over_cap_rows']}",
            f"Authority rows: {audit['authority_rows']}",
            f"Unsafe loss rows: {audit['unsafe_loss_rows']}",
            "",
            "Decoder CE, runtime, Gemma, harness, scoring, source/body emission, and promotion remain closed.",
        ]) + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
