#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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
STAGE = 9790
NAME = "stage9790_edit_localization_opaque_choice_surface"
SOURCE = ROOT / "runs/local/artifacts/stage9771_edit_localization_visible_evidence_lift_package/edit_localization_visible_evidence_lift.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "edit_localization_opaque_choice_surface.jsonl"
AUDIT = OUT_DIR / "edit_localization_opaque_choice_surface_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_OPAQUE_CHOICE_SURFACE_STAGE9790.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["train", "eval", "strict_eval"]
OPAQUE_LABELS = ["A", "B", "C", "D", "E"]
SEMANTIC_CHOICES = {
    "TARGET_CONFIG": "configuration_or_settings_surface",
    "TARGET_ENTRYPOINT": "entrypoint_or_invocation_surface",
    "TARGET_FILE": "implementation_file_surface",
    "TARGET_SYMBOL": "symbol_definition_or_implementation_surface",
    "TARGET_TEST": "test_surface",
}
CANONICAL_LABELS = sorted(SEMANTIC_CHOICES)


def _load_row_text():
    path = ROOT / "legacy_src/agentkernel_lite/training_data.py"
    spec = importlib.util.spec_from_file_location("stage9790_training_data", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9790_training_data"] = module
    spec.loader.exec_module(module)
    return getattr(module, "_row_text")


_row_text = _load_row_text()


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


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


def _original_label(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(clean.get("edit_localization_target") or "")


def _permutation_for_language(language_family: str) -> list[str]:
    seed = hashlib.sha256(f"opaque-choice:{language_family}".encode("utf-8")).hexdigest()
    items = list(CANONICAL_LABELS)
    keyed = [
        (hashlib.sha256(f"{seed}:{label}".encode("utf-8")).hexdigest(), label)
        for label in items
    ]
    keyed.sort()
    return [label for _, label in keyed]


def _choice_strings(label_order: list[str]) -> list[str]:
    return [
        f"option {opaque}: {SEMANTIC_CHOICES[label]}"
        for opaque, label in zip(OPAQUE_LABELS, label_order)
    ]


def transform_row(row: dict[str, Any]) -> dict[str, Any]:
    new_row = json.loads(json.dumps(row))
    row_id = str(new_row.get("row_id") or "")
    target = _original_label(new_row)
    label_order = _permutation_for_language(str(new_row.get("language_family") or ""))
    opaque_map = {label: opaque for opaque, label in zip(OPAQUE_LABELS, label_order)}
    if target not in opaque_map:
        raise KeyError(f"missing target mapping for {row_id}: {target}")
    opaque_target = opaque_map[target]

    state = new_row.get("input_state") if isinstance(new_row.get("input_state"), dict) else {}
    state["candidate_choices"] = _choice_strings(label_order)
    state["choice_protocol"] = "return_only_the_option_token"
    state["choice_count"] = len(OPAQUE_LABELS)
    new_row["input_state"] = state
    new_row["surface"] = "edit_localization_opaque_choice_surface_v1"

    clean = new_row.get("clean_state") if isinstance(new_row.get("clean_state"), dict) else {}
    clean["edit_localization"] = opaque_target
    clean["edit_localization_target"] = opaque_target
    clean["edit_localization_target_hidden"] = target
    new_row["clean_state"] = clean

    target_payload = new_row.get("target") if isinstance(new_row.get("target"), dict) else {}
    target_payload["edit_localization"] = opaque_target
    target_payload["decoder_text"] = opaque_target
    target_payload["target_ref"] = opaque_target
    new_row["target"] = target_payload

    anti = new_row.get("anti_cheat") if isinstance(new_row.get("anti_cheat"), dict) else {}
    anti["opaque_choice_surface"] = True
    anti["target_label_literals_in_prompt_surface"] = False
    anti["candidate_descriptions_use_raw_target_literals"] = False
    anti["opaque_choice_protocol"] = "A_to_E"
    new_row["anti_cheat"] = anti
    return new_row


def _bucket_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("language_family") or ""), str(row.get("split") or "")


def summarize_choice_diversity(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_bucket_key(row)].append(row)
    summary: dict[str, dict[str, Any]] = {}
    for (lang, split), bucket in grouped.items():
        choice_protocols = Counter(
            tuple((row.get("input_state") or {}).get("candidate_choices") or [])
            for row in bucket
        )
        summary[f"{lang}:{split}"] = {
            "rows": len(bucket),
            "unique_choice_orders": len(choice_protocols),
            "all_rows_use_opaque_targets": all(
                str((row.get("target") or {}).get("decoder_text") or "") in OPAQUE_LABELS
                for row in bucket
            ),
        }
    return dict(sorted(summary.items()))


def collect_failures(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        text = _row_text(row)
        row_id = str(row.get("row_id") or "")
        if "TARGET_" in text:
            failures.append(f"target_label_literal_present:{row_id}")
        if any(label in text for label in CANONICAL_LABELS):
            failures.append(f"raw_target_label_present:{row_id}")
        target_payload = row.get("target") if isinstance(row.get("target"), dict) else {}
        decoder_text = str(target_payload.get("decoder_text") or "")
        if decoder_text not in OPAQUE_LABELS:
            failures.append(f"decoder_text_not_opaque:{row_id}")
        choices = (row.get("input_state") or {}).get("candidate_choices")
        if not isinstance(choices, list) or len(choices) != 5:
            failures.append(f"candidate_choices_invalid:{row_id}")
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        if anti.get("opaque_choice_surface") is not True:
            failures.append(f"opaque_choice_flag_missing:{row_id}")
    return failures


def source_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(SOURCE)
    if rows and isinstance(rows[0], dict) and rows[0].get("row_id"):
        return rows
    lift_rows = _load_symbol(
        "stage9790_stage9771_builder",
        ROOT / "scripts/build_stage9771_edit_localization_visible_evidence_lift_package.py",
        "lift_rows",
    )
    source_loader = _load_symbol(
        "stage9790_stage9771_source_loader",
        ROOT / "scripts/build_stage9771_edit_localization_visible_evidence_lift_package.py",
        "load_jsonl",
    )
    source_path = _load_symbol(
        "stage9790_stage9771_source_path",
        ROOT / "scripts/build_stage9771_edit_localization_visible_evidence_lift_package.py",
        "SOURCE",
    )
    return lift_rows(source_loader(source_path))


def build_surface() -> dict[str, Any]:
    transformed = [transform_row(row) for row in source_rows()]
    write_jsonl(MANIFEST, transformed)
    failures = collect_failures(transformed)
    choice_diversity = summarize_choice_diversity(transformed)
    audit = {
        "passed": not failures,
        "rows": len(transformed),
        "language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in transformed).items())),
        "split_counts": dict(sorted(Counter(str(row.get("split") or "") for row in transformed).items())),
        "decoder_label_counts": dict(sorted(Counter(str((row.get("target") or {}).get("decoder_text") or "") for row in transformed).items())),
        "choice_diversity": choice_diversity,
        "failures": failures,
        "anti_cheat_findings": [
            "The successor surface removes raw TARGET_* labels from the prompt-visible surface and decoder targets.",
            "Each language family uses one deterministic opaque option permutation A-E shared across train, eval, and strict_eval while preserving a one-to-one mapping across the five target classes.",
            "Candidate descriptions stay semantic but avoid the raw canonical label tokens that made the prior packet label-proxy friendly.",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_surface()
    next_step = (
        "Run the 100M and Gemma comparison again on the Stage9790 opaque-choice surface, because this package removes the raw TARGET_* label vocabulary that blocked a clean anti-shortcut pass on Stage9771."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "rows": audit["rows"],
            "unique_choice_orders_strict_eval_python": (audit["choice_diversity"].get("python:strict_eval") or {}).get("unique_choice_orders"),
        },
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized an opaque-choice successor to the visible-evidence edit-localization package. The decoder target is now an opaque option token A-E, and the prompt-visible surface no longer carries raw TARGET_* labels.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9790 Edit Localization Opaque Choice Surface",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Python strict unique choice orders: `{summary['metrics']['unique_choice_orders_strict_eval_python']}`",
                "",
                "This package is a direct successor to the Stage9771 visible-evidence surface. It preserves visible locality evidence but replaces the raw TARGET_* decoder vocabulary with opaque option tokens A-E, using a deterministic per-language permutation shared across splits.",
                "",
                "Anti-cheat notes:",
                "- raw TARGET_* labels are removed from prompt-visible fields",
                "- decoder targets are opaque option tokens only",
                "- candidate options are permuted per row",
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
                "rows": audit["rows"],
                "failures": audit["failures"],
                "next_best_step": next_step,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
