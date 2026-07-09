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
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9609
NAME = "stage9609_suffix_continuation_ladder_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9608_prefix_primed_suffix_continuation_failure_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9605_prefix_primed_residual_denoise_manifest/prefix_primed_residual_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "suffix_continuation_ladder_manifest.jsonl"
AUDIT = OUT_DIR / "suffix_continuation_ladder_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CONTINUATION_LADDER_MANIFEST_STAGE9609.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
GENERATION_PREFIX_FIELD = "model_input.active_generation_prefix_span"
PREFIX_WORD_COUNTS = (5, 8)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def nested_value(row: dict[str, Any], path: str) -> Any:
    value: Any = row
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def active_losses(row: dict[str, Any]) -> list[str]:
    loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    return sorted(key for key, value in loss.items() if bool(value))


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in source_rows:
        target = str((source.get("target") or {}).get("decoder_text") or source.get("decoder_text") or "").strip()
        words = target.split()
        for count in PREFIX_WORD_COUNTS:
            if len(words) <= count:
                continue
            prefix = " ".join(words[:count])
            if len(prefix) > 96:
                continue
            row = copy.deepcopy(source)
            model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
            model_input = dict(model_input)
            model_input.update(
                {
                    "active_generation_prefix_span": prefix,
                    "active_generation_prefix_words": count,
                    "suffix_continuation_ladder_stage": STAGE,
                    "suffix_ladder_depth": f"prefix_{count}_words",
                    "second_span_support": count > min(PREFIX_WORD_COUNTS),
                    "anti_repetition_focus": "localized/relevant/inv_loop_after_boundary",
                    "remaining_suffix_hidden_from_model_input": True,
                    "clean_target_hidden_from_model_input": True,
                }
            )
            for key in ["target_text", "clean_target", "decoder_text", "remaining_suffix", "target_suffix", "first_suffix_word"]:
                model_input.pop(key, None)
            loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
            loss_mask = {key: False for key in loss_mask}
            loss_mask["denoise_ce"] = True
            loss_mask.setdefault("decoder_ce", False)
            loss_mask.setdefault("structured_aux", False)
            loss_mask.setdefault("runtime_reward", False)
            anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
            anti = dict(anti)
            anti.update(
                {
                    "decoder_ce_closed": True,
                    "runtime_closed": True,
                    "prefix_visible_but_suffix_hidden": True,
                    "generation_prefix_is_not_full_target": prefix != target,
                    "suffix_ladder_curriculum": True,
                }
            )
            source_id = str(source.get("row_id"))
            row.update(
                {
                    "row_id": f"stage9609_suffix_ladder_{count:02d}_{h(source_id + prefix + target)}",
                    "source_stage9605_row_id": source_id,
                    "objective_family": "suffix_continuation_ladder_v1",
                    "route": "SUFFIX_CONTINUATION_LADDER_DENOISE_CANDIDATE_CLOSED",
                    "model_input": model_input,
                    "target": {
                        **(row.get("target") if isinstance(row.get("target"), dict) else {}),
                        "decoder_text": target,
                        "rendered_from": "stage9605_clean_target_with_ladder_prefix",
                        "prefix_visible_suffix_hidden": True,
                        "target_authority": "stage9609_suffix_ladder_from_stage9605",
                    },
                    "decoder_text": target,
                    "clean_target": target,
                    "loss_mask": loss_mask,
                    "authority": dict(AUTHORITY_CLOSED),
                    "anti_cheat": anti,
                    "generation_prefix_field": GENERATION_PREFIX_FIELD,
                    "target_token_len_estimate": len(words),
                }
            )
            rows.append(row)
    return rows


def audit_rows(rows: list[dict[str, Any]], source_rows: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    split_counts = Counter(str(row.get("split")) for row in rows)
    language_counts = Counter(str(row.get("language_family")) for row in rows)
    ladder_counts = Counter(str(nested_value(row, "model_input.suffix_ladder_depth")) for row in rows)
    prefix_bad: list[dict[str, str]] = []
    target_visible: list[str] = []
    unsafe_rows: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        target = str((row.get("target") or {}).get("decoder_text") or "")
        prefix = str(nested_value(row, GENERATION_PREFIX_FIELD) or "")
        model_input_text = json.dumps(row.get("model_input") or {}, sort_keys=True)
        if not prefix:
            prefix_bad.append({"row_id": row_id, "reason": "missing_prefix"})
        elif len(prefix.split()) > 8 or len(prefix) > 96:
            prefix_bad.append({"row_id": row_id, "reason": "prefix_over_cap"})
        elif prefix == target:
            prefix_bad.append({"row_id": row_id, "reason": "prefix_is_full_target"})
        elif not target.startswith(prefix):
            prefix_bad.append({"row_id": row_id, "reason": "prefix_not_target_start"})
        if target and target in model_input_text:
            target_visible.append(row_id)
        if active_losses(row) != ["denoise_ce"]:
            unsafe_rows.append(row_id)
        if any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9608_not_passed")
    if len(source_rows) != 26:
        failures.append("source_rows_not_26")
    if len(rows) != 52:
        failures.append("ladder_rows_not_52")
    if prefix_bad:
        failures.append("prefix_contract_failures")
    if target_visible:
        failures.append("full_target_visible_in_model_input")
    if unsafe_rows:
        failures.append("unsafe_or_wrong_loss_rows")
    return {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "source_rows": len(source_rows),
        "rows": len(rows),
        "split_counts": dict(split_counts),
        "language_counts": dict(language_counts),
        "ladder_counts": dict(ladder_counts),
        "generation_prefix_field": GENERATION_PREFIX_FIELD,
        "prefix_bad_rows": prefix_bad,
        "full_target_visible_rows": target_visible,
        "unsafe_rows": unsafe_rows,
        "decoder_ce_rows": 0,
        "runtime_rows": 0,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    rows = build_rows(source_rows)
    write_jsonl(MANIFEST, rows)
    audit = audit_rows(rows, source_rows, source)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run Stage9610 contract-only preflight for the suffix-continuation ladder manifest before another tiny execution."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a suffix-continuation ladder manifest that trains later suffix spans with audited active prefixes while keeping decoder CE/runtime/export closed.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9609 Suffix Continuation Ladder Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Ladder counts: `{audit['ladder_counts']}`",
                f"Splits: `{audit['split_counts']}`",
                "",
                "This manifest extends Stage9605 with two active prefix lengths per clean row. It targets the Stage9608 failure mode: the model gets the prefix and first suffix token but repeats local fragments before completing the suffix.",
                "",
                "Decoder CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": audit["failures"], "rows": audit["rows"], "next_best_step": next_step}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
