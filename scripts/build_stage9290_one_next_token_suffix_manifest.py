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
STAGE = 9290
NAME = "stage9290_one_next_token_suffix_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9289_train_generation_memorization_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9282_suffix_step_micro_overfit_manifest/suffix_step_micro_overfit_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "one_next_token_suffix_manifest.jsonl"
AUDIT = OUT_DIR / "one_next_token_suffix_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ONE_NEXT_TOKEN_SUFFIX_MANIFEST_STAGE9290.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MAX_PARTIAL_CHARS = 96
CONTROL_SUFFIX_STOPWORDS = {"repair", "route", "denoise", "runtime", "decoder", "source", "target", "model", "train", "eval", "strict"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text)


def first_suffix_target(full_target: str, priming: str) -> tuple[str, str]:
    if not full_target.startswith(priming):
        return "", ""
    remainder = full_target[len(priming):]
    match = re.search(r"[A-Za-z][A-Za-z0-9_-]*", remainder)
    if not match:
        return "", ""
    suffix = remainder[: match.end()].rstrip()
    partial = (priming + suffix).strip()
    return partial, suffix.strip()


def visible_projection(row: dict[str, Any]) -> str:
    return json.dumps({"input_state": row.get("input_state"), "model_input": row.get("model_input"), "corrupted_output": row.get("corrupted_output"), "loss_mask": row.get("loss_mask")}, sort_keys=True)


def build_rows() -> list[dict[str, Any]]:
    rows = []
    split_cycle = ["train", "train", "train", "eval", "strict_eval", "train"]
    for source in load_jsonl(SOURCE_MANIFEST):
        full_target = str((source.get("target") or {}).get("decoder_text") or source.get("clean_target") or "")
        priming = str((source.get("model_input") or {}).get("bridge_priming_span") or "")
        partial, suffix = first_suffix_target(full_target, priming)
        if not partial or suffix.lower() in CONTROL_SUFFIX_STOPWORDS:
            continue
        row = dict(source)
        row["row_id"] = str(source.get("row_id", "row")).replace("stage9282_suffixstep", "stage9290_onenext")
        row["split"] = split_cycle[len(rows) % len(split_cycle)]
        row["source_stage"] = STAGE
        row["source_manifest_stage"] = 9282
        row["source_repair_row_id"] = source.get("row_id")
        row["objective_family"] = "one_next_token_suffix_micro_overfit"
        row["repair_task_type"] = "bridge_priming_to_one_next_suffix_token"
        row["target"] = {"decoder_text": partial}
        row["clean_target"] = partial
        state = dict(source.get("input_state") if isinstance(source.get("input_state"), dict) else {})
        for key in list(state):
            if key.startswith("continuation_bridge") or key.startswith("target_anchor") or key in {"visible_target_char_count", "visible_target_word_count"}:
                state.pop(key, None)
        for key in list(state):
            value = state.get(key)
            value_text = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            if suffix.lower() in key.lower() or suffix.lower() in value_text.lower():
                state.pop(key, None)
        state.update({
            "one_next_suffix_objective": True,
            "bridge_priming_span": priming,
            "first_suffix_word_hidden_from_model_input": True,
            "first_suffix_word_count": len(words(suffix)),
            "partial_target_char_count": len(partial),
            "full_target_sha256": sha(full_target),
            "partial_target_sha256": sha(partial),
            "full_target_remainder_hidden": True,
        })
        row["input_state"] = state
        model_input = dict(source.get("model_input") if isinstance(source.get("model_input"), dict) else {})
        for key in ["continuation_bridge_span", "anchor_keywords", "visible_target_word_count", "suffix_step_word_count"]:
            model_input.pop(key, None)
        for key in list(model_input):
            value = model_input.get(key)
            value_text = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            if suffix.lower() in key.lower() or suffix.lower() in value_text.lower():
                model_input.pop(key, None)
        model_input.update({
            "target_grounding_mode": "one_next_token_suffix_v1",
            "bridge_priming_span": priming,
            "bridge_priming_then_one_next_suffix": True,
            "full_target_remainder_hidden": True,
        })
        row["model_input"] = model_input
        row["anti_cheat"] = {"bridge_priming_visible": True, "partial_target_in_model_visible_fields": False, "first_suffix_word_visible": False, "decoder_ce_closed": True, "runtime_closed": True, "max_partial_chars": MAX_PARTIAL_CHARS}
        row["loss_mask"] = {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False}
        row["authority"] = dict(AUTHORITY_CLOSED)
        rows.append(row)
    return rows


def audit_rows(rows: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9289_not_passed")
    if not rows:
        failures.append("manifest_empty")
    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    visible_partial = visible_suffix = invalid = over_cap = authority_rows = unsafe_loss = 0
    for row in rows:
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        language_counts[str(row.get("language_family"))] = language_counts.get(str(row.get("language_family")), 0) + 1
        target = str((row.get("target") or {}).get("decoder_text") or "")
        priming = str((row.get("model_input") or {}).get("bridge_priming_span") or "")
        suffix = target[len(priming):].strip() if target.startswith(priming) else ""
        visible = visible_projection(row)
        if target and target in visible:
            visible_partial += 1
        if suffix and suffix in visible:
            visible_suffix += 1
        if not priming or not target.startswith(priming) or len(words(suffix)) != 1:
            invalid += 1
        if len(target) > MAX_PARTIAL_CHARS:
            over_cap += 1
        if any((row.get("authority") or {}).values()):
            authority_rows += 1
        mask = row.get("loss_mask") or {}
        if mask.get("denoise_ce") is not True or mask.get("decoder_ce") is not False or mask.get("runtime_reward") is not False:
            unsafe_loss += 1
    for name, count in [("partial_target_visible_rows", visible_partial), ("first_suffix_visible_rows", visible_suffix), ("invalid_one_next_rows", invalid), ("over_cap_rows", over_cap), ("authority_rows", authority_rows), ("unsafe_loss_rows", unsafe_loss)]:
        if count:
            failures.append(f"{name}_nonzero")
    return {"passed": not failures, "failures": failures, "rows": len(rows), "split_counts": split_counts, "language_counts": language_counts, "partial_target_visible_rows": visible_partial, "first_suffix_visible_rows": visible_suffix, "invalid_one_next_rows": invalid, "over_cap_rows": over_cap, "authority_rows": authority_rows, "unsafe_loss_rows": unsafe_loss, "authority": dict(AUTHORITY_CLOSED)}


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
    audit = audit_rows(rows, load_json(SOURCE_SUMMARY))
    MANIFEST.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Built one-next-token suffix rows to test the smallest possible autoregressive continuation after bridge priming.", "next_best_step": "Run contract preflight and a tiny one-next-token suffix denoise probe with train generation audit.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9290 One Next Token Suffix Manifest", "", f"Rows: {audit['rows']}", f"Splits: {audit['split_counts']}", f"Partial target visible rows: {audit['partial_target_visible_rows']}", f"First suffix visible rows: {audit['first_suffix_visible_rows']}", "Decoder CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.", ""]) , encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
