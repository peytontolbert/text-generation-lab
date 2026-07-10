#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9789
NAME = "stage9789_winning_edit_localization_shortcut_surface_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "winning_edit_localization_shortcut_surface_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WINNING_EDIT_LOCALIZATION_SHORTCUT_SURFACE_AUDIT_STAGE9789.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


RUNNER = _load_symbol(
    "stage9789_runner_module",
    ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py",
    "build_prompt",
)
RUNNER_MODULE = sys.modules["stage9789_runner_module"]
ROW_TEXT = _load_symbol(
    "stage9789_training_data",
    ROOT / "legacy_src/agentkernel_lite/training_data.py",
    "_row_text",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    stripped_lines = [line for line in text.splitlines() if line.strip()]
    try:
        return [json.loads(line) for line in stripped_lines]
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        rows: list[dict[str, Any]] = []
        idx = 0
        while idx < len(text):
            while idx < len(text) and text[idx].isspace():
                idx += 1
            if idx >= len(text):
                break
            value, idx = decoder.raw_decode(text, idx)
            rows.append(value)
        return rows


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


def packet_index() -> dict[str, dict[str, Any]]:
    return {str(row.get("cell_key") or ""): row for row in load_jsonl(PACKETS)}


def _contains_any(text: str, labels: list[str]) -> list[str]:
    return [label for label in labels if label in text]


def build_audit() -> dict[str, Any]:
    packets = packet_index()
    failures: list[str] = []
    records: list[dict[str, Any]] = []
    for lang in LANGS:
        cell_key = f"standalone_100m_weights::{lang}::edit_localization"
        packet = packets.get(cell_key)
        if not isinstance(packet, dict):
            failures.append(f"missing_packet:{cell_key}")
            continue
        rows = RUNNER_MODULE.load_packet_rows(packet)
        strict_rows = [row for row in rows if str(row.get("split") or "") == "strict_eval"]
        if len(strict_rows) != 5:
            failures.append(f"unexpected_strict_row_count:{cell_key}:{len(strict_rows)}")
            continue
        labels = RUNNER_MODULE.label_vocab(rows, "edit_localization")
        row_cards: list[dict[str, Any]] = []
        encoder_expected_mentions = 0
        encoder_any_label_mentions = 0
        identifier_target_mentions = 0
        prompt_valid_label_line_mentions = 0
        prompt_expected_mentions_outside_label_line = 0
        for row in strict_rows:
            expected = RUNNER_MODULE._clean_value(row, "edit_localization") or ""
            prompt = RUNNER(row=row, field="edit_localization", labels=labels)
            encoder_surface = ROW_TEXT(row)
            valid_label_line = f"Valid labels: {', '.join(labels)}"
            encoder_mentions = _contains_any(encoder_surface, labels)
            prompt_without_label_line = prompt.replace(valid_label_line, "")
            expected_in_encoder = expected in encoder_surface
            expected_outside_label_line = expected in prompt_without_label_line
            id_text = " ".join(
                [
                    str(row.get("row_id") or ""),
                    str(row.get("semantic_key") or ""),
                    json.dumps(row.get("query") or {}, sort_keys=True),
                    json.dumps(row.get("graph_input") or {}, sort_keys=True),
                ]
            )
            identifier_mentions = _contains_any(id_text, labels)
            encoder_expected_mentions += int(expected_in_encoder)
            encoder_any_label_mentions += int(bool(encoder_mentions))
            identifier_target_mentions += int(bool(identifier_mentions))
            prompt_valid_label_line_mentions += int(valid_label_line in prompt)
            prompt_expected_mentions_outside_label_line += int(expected_outside_label_line)
            row_cards.append(
                {
                    "row_id": row.get("row_id"),
                    "expected_label": expected,
                    "encoder_surface_contains_expected_label": expected_in_encoder,
                    "encoder_surface_label_mentions": encoder_mentions,
                    "prompt_contains_valid_label_line": valid_label_line in prompt,
                    "prompt_contains_expected_label_outside_valid_label_line": expected_outside_label_line,
                    "identifier_target_mentions": identifier_mentions,
                }
            )
        records.append(
            {
                "cell_key": cell_key,
                "language_family": lang,
                "labels": labels,
                "strict_row_count": len(strict_rows),
                "row_cards": row_cards,
                "metrics": {
                    "encoder_rows_with_expected_label_mentions": encoder_expected_mentions,
                    "encoder_rows_with_any_label_mentions": encoder_any_label_mentions,
                    "identifier_records_with_target_mentions": identifier_target_mentions,
                    "prompt_rows_with_valid_label_line": prompt_valid_label_line_mentions,
                    "prompt_rows_with_expected_label_mentions_outside_label_line": prompt_expected_mentions_outside_label_line,
                },
                "surface_shortcut_findings": [
                    "valid_label_vocab_exposed_in_prompt" if prompt_valid_label_line_mentions == len(strict_rows) else "label_vocab_not_uniformly_exposed",
                    "encoder_surface_expected_label_mentions_absent" if encoder_expected_mentions == 0 else "encoder_surface_expected_label_mentions_present",
                    "opaque_ids_clean" if identifier_target_mentions == 0 else "identifier_target_mentions_present",
                    "expected_label_not_repeated_outside_label_line" if prompt_expected_mentions_outside_label_line == 0 else "expected_label_repeated_outside_label_line",
                ],
                "anti_cheat_gate_recommendation": {
                    "opaque_label_surface_clean": False,
                    "label_proxy_shortcuts_pass_recommended": False,
                    "reason": "the prompt explicitly exposes the full valid label vocabulary on every strict-eval row",
                },
            }
        )

    metrics = {
        "validated_cells": len(records),
        "cells_with_prompt_label_vocab_exposed": sum(
            1
            for row in records
            if row["metrics"]["prompt_rows_with_valid_label_line"] == row["strict_row_count"]
        ),
        "cells_with_encoder_label_mentions": sum(
            1
            for row in records
            if row["metrics"]["encoder_rows_with_any_label_mentions"] > 0
        ),
        "cells_with_clean_opaque_ids": sum(
            1
            for row in records
            if row["metrics"]["identifier_records_with_target_mentions"] == 0
        ),
    }
    if metrics["validated_cells"] != 4:
        failures.append("validated_cells_not_4")
    if metrics["cells_with_prompt_label_vocab_exposed"] != 4:
        failures.append("expected_label_vocab_exposed_in_all_winning_cells")
    if metrics["cells_with_clean_opaque_ids"] != 4:
        failures.append("expected_clean_opaque_ids_in_all_winning_cells")

    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Treat the current visible-evidence winning packet as not opaque-label clean: rebuild the comparison surface so the model cannot rely on the explicit valid-label list, then rerun the anti-shortcut audit before upgrading the win claim."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Audited the winning visible-evidence edit-localization prompt surface and found that while opaque identifiers stay clean, the prompt explicitly exposes the full valid label vocabulary on every strict-eval row, so the packet is not opaque-label clean and should not pass the label-proxy anti-cheat gate.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9789 Winning Edit Localization Shortcut Surface Audit",
                "",
                f"Passed: `{summary['passed']}`",
                f"Validated cells: `{built['metrics']['validated_cells']}`",
                f"Cells with prompt label-vocab exposure: `{built['metrics']['cells_with_prompt_label_vocab_exposed']}`",
                f"Cells with clean opaque ids: `{built['metrics']['cells_with_clean_opaque_ids']}`",
                "",
                "This stage is a prompt-surface audit, not a model rerun. It checks whether the winning visible-evidence packet itself leaks shortcut-friendly structure. The key result is that the prompt builder exposes the full valid-label vocabulary in plain text on every strict-eval row, so the current packet should not be treated as opaque-label clean.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": built["metrics"],
                "failures": built["failures"],
                "next_best_step": next_step,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
