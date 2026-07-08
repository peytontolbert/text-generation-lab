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
STAGE = 9277
NAME = "stage9277_continuation_bridge_denoise_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9276_prefix_primed_denoise_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9274_prefix_copy_denoise_manifest/prefix_copy_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "continuation_bridge_denoise_manifest.jsonl"
BRIDGE_CARD = OUT_DIR / "continuation_bridge_card.json"
AUDIT = OUT_DIR / "continuation_bridge_denoise_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONTINUATION_BRIDGE_DENOISE_MANIFEST_STAGE9277.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUTHORITY_FALSE = dict(AUTHORITY_CLOSED)
MAX_PREFIX_WORDS = 5
MAX_BRIDGE_WORDS = 5
MAX_VISIBLE_TARGET_WORDS = 10
MAX_VISIBLE_TARGET_CHARS = 128
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


def continuation_bridge(target: str, prefix: str) -> str:
    if not target.startswith(prefix):
        return ""
    suffix = target[len(prefix):]
    matches = list(re.finditer(r"[A-Za-z][A-Za-z0-9_-]*", suffix))
    if not matches:
        return ""
    end = matches[min(MAX_BRIDGE_WORDS, len(matches)) - 1].end()
    return suffix[:end].strip()


def visible_target_start(target: str, prefix: str, bridge: str) -> str:
    if not prefix or not bridge or not target.startswith(prefix):
        return ""
    suffix = target[len(prefix):]
    bridge_index = suffix.find(bridge)
    if bridge_index < 0:
        return ""
    return (prefix + suffix[: bridge_index + len(bridge)]).strip()


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
    rows: list[dict[str, Any]] = []
    for source in load_jsonl(SOURCE_MANIFEST):
        target = str((source.get("target") or {}).get("decoder_text") or source.get("clean_target") or "")
        model_input = dict(source.get("model_input") if isinstance(source.get("model_input"), dict) else {})
        prefix = str(model_input.get("copy_prefix_span") or "")
        bridge = continuation_bridge(target, prefix)
        row = dict(source)
        row["row_id"] = str(source.get("row_id", "row")).replace("stage9274_prefixcopy_", "stage9277_bridge_")
        row["source_stage"] = STAGE
        row["source_manifest_stage"] = 9274
        row["source_repair_row_id"] = source.get("row_id")
        row["objective_family"] = "continuation_bridge_bounded_decoder_output_repair"
        row["repair_task_type"] = f"continuation_bridge_{source.get('repair_task_type', 'denoise_repair')}"
        state = dict(source.get("input_state") if isinstance(source.get("input_state"), dict) else {})
        visible_words = words(prefix) + words(bridge)
        state.update({
            "prefix_copy_required": True,
            "continuation_bridge_required": True,
            "approved_prefix_span": prefix,
            "continuation_bridge_span": bridge,
            "visible_target_word_count": len(visible_words),
            "visible_target_char_count": len((prefix + " " + bridge).strip()),
            "target_remainder_hidden": True,
            "target_text_sha256": sha(target),
        })
        row["input_state"] = state
        model_input.update({
            "target_grounding_mode": "continuation_bridge_v1",
            "copy_prefix_span": prefix,
            "continuation_bridge_span": bridge,
            "copy_prefix_then_bridge_then_continue": True,
            "visible_target_word_count": len(visible_words),
        })
        row["model_input"] = model_input
        row["anti_cheat"] = {
            "full_target_text_in_model_visible_fields": False,
            "approved_prefix_visible": True,
            "continuation_bridge_visible": True,
            "target_remainder_hidden": True,
            "max_prefix_words": MAX_PREFIX_WORDS,
            "max_bridge_words": MAX_BRIDGE_WORDS,
            "max_visible_target_words": MAX_VISIBLE_TARGET_WORDS,
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
        failures.append("source_stage9276_not_passed")
    if not rows:
        failures.append("manifest_empty")
    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    full_target_visible_rows = 0
    prefix_visible_rows = 0
    bridge_visible_rows = 0
    remainder_visible_rows = 0
    invalid_bridge_rows = 0
    excessive_visible_rows = 0
    authority_rows = 0
    unsafe_loss_rows = 0
    forbidden_key_rows = 0
    bridge_cards: list[dict[str, Any]] = []
    for row in rows:
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        language_counts[str(row.get("language_family"))] = language_counts.get(str(row.get("language_family")), 0) + 1
        target = str((row.get("target") or {}).get("decoder_text", ""))
        state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        prefix = str(state.get("approved_prefix_span") or "")
        bridge = str(state.get("continuation_bridge_span") or "")
        visible = visible_projection(row)
        if target and target in visible:
            full_target_visible_rows += 1
        if prefix and prefix in visible:
            prefix_visible_rows += 1
        if bridge and bridge in visible:
            bridge_visible_rows += 1
        combined = visible_target_start(target, prefix, bridge)
        if not combined or not target.startswith(combined):
            invalid_bridge_rows += 1
        remainder = target[len(combined):].strip() if combined and target.startswith(combined) else target
        if remainder and len(remainder) > 16 and remainder in visible:
            remainder_visible_rows += 1
        if len(words(prefix)) > MAX_PREFIX_WORDS or len(words(bridge)) > MAX_BRIDGE_WORDS or len(words(combined)) > MAX_VISIBLE_TARGET_WORDS or len(combined) > MAX_VISIBLE_TARGET_CHARS or combined == target:
            excessive_visible_rows += 1
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        if mask.get("denoise_ce") is not True or mask.get("decoder_ce") is not False or mask.get("runtime_reward") is not False:
            unsafe_loss_rows += 1
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else row
        if any(bool(auth.get(key, False)) for key in AUTHORITY_CLOSED):
            authority_rows += 1
        if set(row).intersection(FORBIDDEN_TOP_LEVEL):
            forbidden_key_rows += 1
        bridge_cards.append({
            "row_id": row.get("row_id"),
            "split": row.get("split"),
            "language_family": row.get("language_family"),
            "approved_prefix_span": prefix,
            "continuation_bridge_span": bridge,
            "visible_target_word_count": len(words(combined)),
            "visible_target_char_count": len(combined),
            "target_sha256": sha(target),
        })
    if full_target_visible_rows:
        failures.append("full_target_visible_rows_nonzero")
    if prefix_visible_rows != len(rows):
        failures.append("prefix_not_visible_for_all_rows")
    if bridge_visible_rows != len(rows):
        failures.append("bridge_not_visible_for_all_rows")
    if remainder_visible_rows:
        failures.append("target_remainder_visible_rows_nonzero")
    if invalid_bridge_rows:
        failures.append("invalid_bridge_rows_nonzero")
    if excessive_visible_rows:
        failures.append("excessive_visible_rows_nonzero")
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows_nonzero")
    if forbidden_key_rows:
        failures.append("forbidden_key_rows_nonzero")
    serialized_visible = "\n".join(visible_projection(row).lower() for row in rows)
    for token in ["/arxiv", "hidden_eval", "locked_eval", "runtime_authorized\": true", "gemma_execution_authorized_next\": true"]:
        if token in serialized_visible:
            failures.append(f"forbidden_visible_token:{token}")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "full_target_visible_rows": full_target_visible_rows,
        "prefix_visible_rows": prefix_visible_rows,
        "bridge_visible_rows": bridge_visible_rows,
        "target_remainder_visible_rows": remainder_visible_rows,
        "invalid_bridge_rows": invalid_bridge_rows,
        "excessive_visible_rows": excessive_visible_rows,
        "authority_rows": authority_rows,
        "unsafe_loss_rows": unsafe_loss_rows,
        "forbidden_key_rows": forbidden_key_rows,
        "max_visible_target_words": MAX_VISIBLE_TARGET_WORDS,
        "max_visible_target_chars": MAX_VISIBLE_TARGET_CHARS,
        "bridge_cards": bridge_cards,
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
    BRIDGE_CARD.write_text(json.dumps(audit["bridge_cards"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit_public = {key: value for key, value in audit.items() if key != "bridge_cards"}
    AUDIT.write_text(json.dumps(audit_public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_FALSE,
        "metrics": {**AUTHORITY_FALSE, **audit_public},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "bridge_card": str(BRIDGE_CARD.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built continuation-bridge denoise rows that expose a capped post-prefix span while keeping the target remainder hidden.",
        "next_best_step": "Run a contract-only preflight, then a tiny target-100M continuation-bridge denoise probe with prefix priming and audit target-prefix continuation, EOS, repetition, and leaks.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9277 Continuation-Bridge Denoise Manifest",
            "",
            "Stage9277 exposes a capped prefix plus first continuation bridge while hiding the rest of the target.",
            "",
            f"Rows: {audit['rows']}",
            f"Splits: {audit['split_counts']}",
            f"Prefix visible rows: {audit['prefix_visible_rows']}",
            f"Bridge visible rows: {audit['bridge_visible_rows']}",
            f"Full target visible rows: {audit['full_target_visible_rows']}",
            f"Target remainder visible rows: {audit['target_remainder_visible_rows']}",
            f"Excessive visible rows: {audit['excessive_visible_rows']}",
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
