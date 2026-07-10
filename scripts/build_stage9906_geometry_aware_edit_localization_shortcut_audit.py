#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9906
NAME = "stage9906_geometry_aware_edit_localization_shortcut_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "geometry_aware_edit_localization_shortcut_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GEOMETRY_AWARE_EDIT_LOCALIZATION_SHORTCUT_AUDIT_STAGE9906.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9893_current_margin_locality_signal_label_remap_manifest/current_margin_locality_signal_label_remap_manifest.jsonl"
COMPARISON = ROOT / "runs/local/artifacts/stage9901_geometry_aware_edit_localization_gemma_comparison/geometry_aware_edit_localization_gemma_comparison.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
FIELD = "edit_localization"


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


build_prompt = _load_symbol(
    "stage9906_stage9748_runner",
    ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py",
    "build_prompt",
)
label_vocab = _load_symbol(
    "stage9906_stage9901_comparison",
    ROOT / "scripts/build_stage9901_geometry_aware_edit_localization_gemma_comparison.py",
    "label_vocab",
)
ROW_TEXT = _load_symbol(
    "stage9906_training_data",
    ROOT / "legacy_src/agentkernel_lite/training_data.py",
    "_row_text",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


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


def expected_label(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(target.get("decoder_text") or target.get("edit_localization") or clean.get("edit_localization") or row.get("edit_localization") or "")


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or "")


def row_split(row: dict[str, Any]) -> str:
    return str(row.get("split") or "")


def _contains_any(text: str, labels: list[str]) -> list[str]:
    return [label for label in labels if label in text]


def option_order_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_position_counts = defaultdict(Counter)
    fixed_label_order_rows = 0
    for row in rows:
        labels_in_order: list[str] = []
        pos = None
        tgt = expected_label(row)
        choices = ((row.get("input_state") or {}).get("candidate_choices") or []) if isinstance(row.get("input_state"), dict) else []
        for idx, choice in enumerate(choices):
            prefix = str(choice).split(":", 1)[0].strip().replace("option ", "")
            labels_in_order.append(prefix)
            if prefix == tgt:
                pos = idx
        if labels_in_order == ["K", "M", "R", "T", "Z"]:
            fixed_label_order_rows += 1
        if pos is not None:
            target_position_counts[tgt][pos] += 1
    return {
        "fixed_label_order_rows": fixed_label_order_rows,
        "all_rows_use_fixed_label_order": fixed_label_order_rows == len(rows),
        "target_position_counts": {label: dict(sorted(counts.items())) for label, counts in sorted(target_position_counts.items())},
        "target_position_is_singleton_for_every_label": all(len(counts) == 1 for counts in target_position_counts.values()),
    }


def build_audit() -> dict[str, Any]:
    comparison = load_json(COMPARISON)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if not rows:
        failures.append("missing_manifest_rows")
    if comparison.get("passed") is not True:
        failures.append("stage9901_comparison_not_passed")
    labels = label_vocab(rows) if rows else []
    records: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        lang = row_language(row)
        split = row_split(row)
        if lang in LANGS and split in {"eval", "strict_eval"}:
            grouped[(lang, split)].append(row)
    for key in grouped:
        grouped[key].sort(key=lambda row: str(row.get("row_id") or ""))
    for lang in LANGS:
        for split in ("eval", "strict_eval"):
            bucket = grouped.get((lang, split), [])
            if not bucket:
                failures.append(f"missing_bucket:{lang}:{split}")
                continue
            prompt_valid_label_line_mentions = 0
            prompt_expected_mentions_outside_label_line = 0
            encoder_expected_mentions = 0
            encoder_any_label_mentions = 0
            identifier_target_mentions = 0
            row_cards: list[dict[str, Any]] = []
            for row in bucket:
                prompt = build_prompt(row=row, field=FIELD, labels=labels)
                encoder_surface = ROW_TEXT(row)
                expected = expected_label(row)
                valid_label_line = f"Valid labels: {', '.join(labels)}"
                prompt_without_label_line = prompt.replace(valid_label_line, "")
                encoder_mentions = _contains_any(encoder_surface, labels)
                identifier_text = " ".join(
                    [
                        str(row.get("row_id") or ""),
                        str(row.get("semantic_key") or ""),
                        json.dumps(row.get("query") or {}, sort_keys=True),
                        json.dumps(row.get("graph_input") or {}, sort_keys=True),
                    ]
                )
                identifier_mentions = _contains_any(identifier_text, labels)
                expected_in_encoder = expected in encoder_surface
                expected_outside_label_line = expected in prompt_without_label_line
                prompt_valid_label_line_mentions += int(valid_label_line in prompt)
                prompt_expected_mentions_outside_label_line += int(expected_outside_label_line)
                encoder_expected_mentions += int(expected_in_encoder)
                encoder_any_label_mentions += int(bool(encoder_mentions))
                identifier_target_mentions += int(bool(identifier_mentions))
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
                    "language_family": lang,
                    "split": split,
                    "labels": labels,
                    "rows": len(bucket),
                    "row_cards": row_cards,
                    "metrics": {
                        "prompt_rows_with_valid_label_line": prompt_valid_label_line_mentions,
                        "prompt_rows_with_expected_label_mentions_outside_label_line": prompt_expected_mentions_outside_label_line,
                        "encoder_rows_with_expected_label_mentions": encoder_expected_mentions,
                        "encoder_rows_with_any_label_mentions": encoder_any_label_mentions,
                        "identifier_records_with_target_mentions": identifier_target_mentions,
                    },
                    "surface_shortcut_findings": [
                        "valid_label_vocab_exposed_in_prompt" if prompt_valid_label_line_mentions == len(bucket) else "label_vocab_not_uniformly_exposed",
                        "encoder_surface_expected_label_mentions_absent" if encoder_expected_mentions == 0 else "encoder_surface_expected_label_mentions_present",
                        "opaque_ids_clean" if identifier_target_mentions == 0 else "identifier_target_mentions_present",
                        "expected_label_not_repeated_outside_label_line" if prompt_expected_mentions_outside_label_line == 0 else "expected_label_repeated_outside_label_line",
                    ],
                }
            )
    ordering = option_order_metrics(rows)
    metrics = {
        "validated_buckets": len(records),
        "labels": labels,
        "buckets_with_prompt_label_vocab_exposed": sum(1 for row in records if row["metrics"]["prompt_rows_with_valid_label_line"] == row["rows"]),
        "buckets_with_clean_opaque_ids": sum(1 for row in records if row["metrics"]["identifier_records_with_target_mentions"] == 0),
        "buckets_with_encoder_label_mentions": sum(1 for row in records if row["metrics"]["encoder_rows_with_any_label_mentions"] > 0),
        "all_rows_use_fixed_label_order": ordering["all_rows_use_fixed_label_order"],
        "target_position_is_singleton_for_every_label": ordering["target_position_is_singleton_for_every_label"],
        "target_position_counts": ordering["target_position_counts"],
        "comparison_wins_100m": comparison.get("wins_100m"),
        "comparison_wins_gemma": comparison.get("wins_gemma"),
        "comparison_ties": comparison.get("ties"),
    }
    if metrics["validated_buckets"] != 8:
        failures.append("validated_buckets_not_8")
    if metrics["buckets_with_prompt_label_vocab_exposed"] != 8:
        failures.append("expected_label_vocab_exposed_in_all_buckets")
    if metrics["buckets_with_clean_opaque_ids"] != 8:
        failures.append("expected_clean_opaque_ids_in_all_buckets")
    gate = {
        "opaque_label_surface_clean": False,
        "label_proxy_shortcuts_pass_recommended": False,
        "same_surface_claim_hardened": False,
        "reason": "the current geometry-aware comparison still exposes the full valid label vocabulary in the prompt, so the same-surface margin remains vulnerable to label-proxy shortcuts even though candidate positions are no longer fixed to one slot per label",
    }
    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "metrics": metrics,
        "gate_recommendation": gate,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Do not upgrade Stage9901 into a robust multilingual win claim. Rebuild the current geometry-aware comparison surface so prompts do not reveal the valid label list and candidate IDs are row-randomized or hidden behind constrained opaque outputs, then rerun the same-surface Gemma comparison."
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
        "decision": "Audited the current geometry-aware edit-localization comparison surface and found that the prompt still exposes the full label vocabulary on every bucket. Candidate positions are no longer fully fixed, but the current same-surface margin is still not hardened against label-proxy shortcuts.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9906 Geometry-Aware Edit Localization Shortcut Audit",
                "",
                f"Passed: `{summary['passed']}`",
                f"Validated buckets: `{built['metrics']['validated_buckets']}`",
                f"Prompt exposes valid-label line in all buckets: `{built['metrics']['buckets_with_prompt_label_vocab_exposed'] == built['metrics']['validated_buckets']}`",
                f"All rows use fixed label order: `{built['metrics']['all_rows_use_fixed_label_order']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "validated_buckets": built["metrics"]["validated_buckets"],
                "buckets_with_prompt_label_vocab_exposed": built["metrics"]["buckets_with_prompt_label_vocab_exposed"],
                "all_rows_use_fixed_label_order": built["metrics"]["all_rows_use_fixed_label_order"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
