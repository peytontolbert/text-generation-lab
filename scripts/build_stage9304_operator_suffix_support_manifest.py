#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9304
NAME = "stage9304_operator_suffix_support_manifest"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9290_one_next_token_suffix_manifest/one_next_token_suffix_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9303_causal_mask_boundary_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "operator_suffix_support_manifest.jsonl"
AUDIT = OUT_DIR / "operator_suffix_support_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_SUFFIX_SUPPORT_MANIFEST_STAGE9304.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def first_suffix_word(row: dict[str, Any]) -> str:
    target = str(((row.get("target") or {}).get("decoder_text")) or row.get("clean_target") or "")
    bridge = str(((row.get("model_input") or {}).get("bridge_priming_span")) or "")
    if bridge and target.startswith(bridge):
        remainder = target[len(bridge):].strip()
    else:
        remainder = target
    return remainder.split()[0] if remainder.split() else ""


def support_key(row: dict[str, Any]) -> str:
    return first_suffix_word(row).lower()


def build_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [copy.deepcopy(row) for row in source_rows]
    eval_operator = next(
        (
            row
            for row in source_rows
            if row.get("split") == "eval"
            and support_key(row) == "operator"
        ),
        None,
    )
    if eval_operator is None:
        raise RuntimeError("source manifest does not contain the eval operator suffix row")
    support = copy.deepcopy(eval_operator)
    support["row_id"] = f"stage9304_operator_support_train_{eval_operator['row_id']}"
    support["split"] = "train"
    support["source_stage"] = STAGE
    support["source_manifest_stage"] = 9304
    support["objective_family"] = "one_next_token_suffix_supported_micro_overfit"
    support["diagnostic_support_row"] = True
    support["diagnostic_support_for_row_id"] = eval_operator["row_id"]
    support.setdefault("input_state", {})["operator_suffix_train_support"] = True
    support.setdefault("input_state", {})["support_row_intent"] = "make eval operator suffix train-visible for causal-mask boundary diagnostics"
    support.setdefault("model_input", {})["target_grounding_mode"] = "one_next_token_suffix_supported_v1"
    support.setdefault("anti_cheat", {})["exact_target_overlap_intentional_for_boundary_support_probe"] = True
    rows.insert(4, support)
    return rows


def audit_rows(rows: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("source_stage9303_not_passed")
    if len(rows) != 7:
        failures.append("row_count_not_7")
    split_counts = Counter(str(row.get("split")) for row in rows)
    if split_counts != {"train": 5, "eval": 1, "strict_eval": 1}:
        failures.append("unexpected_split_counts")
    authority_rows = sum(1 for row in rows if any(bool(v) for v in (row.get("authority") or {}).values()))
    unsafe_loss_rows = sum(1 for row in rows if (row.get("loss_mask") or {}).get("decoder_ce") or not (row.get("loss_mask") or {}).get("denoise_ce"))
    visible_suffix_rows = sum(1 for row in rows if not (row.get("input_state") or {}).get("first_suffix_word_hidden_from_model_input"))
    partial_visible_rows = sum(1 for row in rows if not (row.get("anti_cheat") or {}).get("partial_target_in_model_visible_fields") is False)
    support_rows = [row for row in rows if row.get("diagnostic_support_row")]
    if len(support_rows) != 1:
        failures.append("operator_support_row_count_not_1")
    if authority_rows:
        failures.append("authority_rows_present")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows_present")
    if visible_suffix_rows:
        failures.append("first_suffix_visible_rows_present")
    if partial_visible_rows:
        failures.append("partial_target_visible_rows_present")
    support_by_split: dict[str, set[str]] = defaultdict(set)
    rows_by_suffix_split: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        split = str(row.get("split"))
        key = support_key(row)
        support_by_split[split].add(key)
        rows_by_suffix_split[key][split] += 1
    train_suffixes = support_by_split.get("train", set())
    unsupported_eval_suffixes = sorted(key for key in support_by_split.get("eval", set()) if key not in train_suffixes)
    unsupported_strict_suffixes = sorted(key for key in support_by_split.get("strict_eval", set()) if key not in train_suffixes)
    if unsupported_eval_suffixes:
        failures.append("eval_suffix_not_train_supported")
    if unsupported_strict_suffixes:
        failures.append("strict_suffix_not_train_supported")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(split_counts),
        "language_counts": dict(Counter(str(row.get("language_family")) for row in rows)),
        "suffix_support_by_split": {split: sorted(values) for split, values in support_by_split.items()},
        "rows_by_suffix_split": {key: dict(counter) for key, counter in sorted(rows_by_suffix_split.items())},
        "unsupported_eval_suffixes": unsupported_eval_suffixes,
        "unsupported_strict_suffixes": unsupported_strict_suffixes,
        "authority_rows": authority_rows,
        "unsafe_loss_rows": unsafe_loss_rows,
        "first_suffix_visible_rows": visible_suffix_rows,
        "partial_target_visible_rows": partial_visible_rows,
        "diagnostic_support_rows": len(support_rows),
        "exact_target_overlap_intentional": True,
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
    source_rows = load_jsonl(SOURCE_MANIFEST)
    rows = build_rows(source_rows)
    write_jsonl(MANIFEST, rows)
    audit = audit_rows(rows, load_json(SOURCE_SUMMARY))
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
        "decision": "Added one explicit train support row for the eval operator suffix so the next causal-mask boundary diagnostic tests supported suffix recovery, not a held-out suffix class.",
        "next_best_step": "Build a controlled preexecution wrapper for the Stage9305 supported-suffix boundary probe; keep decoder CE/runtime/Gemma/harness closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9304 Operator Suffix Support Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{audit['split_counts']}`",
                f"Manifest SHA256: `{audit['manifest_sha256']}`",
                "",
                "This is a supported-suffix boundary diagnostic, not a generalization claim.",
                "The new train support row intentionally exposes the previously held-out `operator` suffix class to training while keeping the first suffix word hidden from model input.",
                "Decoder CE, runtime, Gemma, harness, source/body emission, and promotion remain closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
