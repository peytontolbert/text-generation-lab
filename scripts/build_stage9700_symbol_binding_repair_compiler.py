#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9700
NAME = "stage9700_symbol_binding_repair_compiler"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9699_symbol_binding_postrun_diagnostics.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9695_multisurface_structured_tiny_execution_review/tiny_structured_manifests/symbol_binding_tiny.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REPAIRED_MANIFEST = OUT_DIR / "symbol_binding_tiny_rebalanced.jsonl"
AUDIT = OUT_DIR / "symbol_binding_repair_compiler_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_REPAIR_COMPILER_STAGE9700.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def target_label(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    label = clean.get("binding_action") or clean.get("symbol_binding") or target.get("binding_action") or target.get("symbol_binding") or row.get("binding_action")
    if not label:
        raise ValueError(f"missing binding label for row {row.get('row_id')}")
    return str(label)


def update_semantic_key(row: dict[str, Any], split: str) -> None:
    key = row.get("semantic_key")
    if isinstance(key, str) and ":" in key:
        row["semantic_key"] = split + ":" + key.split(":", 1)[1]


def balanced_split_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_label[target_label(row)].append(row)
    repaired: list[dict[str, Any]] = []
    for label in sorted(by_label):
        label_rows = sorted(by_label[label], key=lambda row: str(row.get("row_id") or ""))
        per_eval = max(1, round(len(label_rows) / 4))
        per_strict = max(1, round(len(label_rows) / 4))
        if per_eval + per_strict >= len(label_rows):
            per_eval = max(1, len(label_rows) // 3)
            per_strict = max(1, len(label_rows) // 3)
        split_plan = (
            ["eval"] * per_eval
            + ["strict_eval"] * per_strict
            + ["train"] * (len(label_rows) - per_eval - per_strict)
        )
        for row, split in zip(label_rows, split_plan):
            out = deepcopy(row)
            out["split"] = split
            update_semantic_key(out, split)
            repair_meta = out.setdefault("stage9700_repair", {})
            repair_meta["source_split"] = row.get("split")
            repair_meta["repair"] = "rebalanced_symbol_binding_label_coverage"
            repair_meta["target_label"] = label
            repaired.append(out)
    return sorted(repaired, key=lambda row: (str(row.get("split")), target_label(row), str(row.get("row_id"))))


def split_label_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        counts[str(row.get("split") or "unknown")][target_label(row)] += 1
    return {split: dict(counter) for split, counter in counts.items()}


def count_enabled_losses(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for name, enabled in mask.items():
            if enabled:
                counts[name] += 1
    return counts


def authority_violations(rows: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for row in rows:
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key, value in authority.items():
            if value:
                violations.append(f"{row.get('row_id')}:{key}")
    return violations


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    repaired = balanced_split_rows(source_rows)
    write_jsonl(REPAIRED_MANIFEST, repaired)

    source_row_ids = Counter(str(row.get("row_id")) for row in source_rows)
    repaired_row_ids = Counter(str(row.get("row_id")) for row in repaired)
    source_counts = split_label_counts(source_rows)
    repaired_counts = split_label_counts(repaired)
    all_labels = sorted({target_label(row) for row in repaired})
    missing_by_split = {
        split: sorted(set(all_labels) - set(repaired_counts.get(split, {})))
        for split in ["train", "eval", "strict_eval"]
    }
    loss_counts = count_enabled_losses(repaired)
    violations = authority_violations(repaired)
    moved_rows = sum(1 for row in repaired if (row.get("stage9700_repair") or {}).get("source_split") != row.get("split"))

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9699_not_passed")
    if len(source_rows) != 64 or len(repaired) != 64:
        failures.append("unexpected_row_count")
    if source_row_ids != repaired_row_ids:
        failures.append("row_identity_not_preserved")
    expected_split_sizes = {"train": 32, "eval": 16, "strict_eval": 16}
    actual_split_sizes = Counter(str(row.get("split")) for row in repaired)
    if dict(actual_split_sizes) != expected_split_sizes:
        failures.append(f"unexpected_split_sizes:{dict(actual_split_sizes)}")
    if any(missing_by_split.values()):
        failures.append(f"missing_labels_by_split:{missing_by_split}")
    if violations:
        failures.append(f"authority_violations:{violations[:5]}")
    if loss_counts != Counter({"symbol_binding_ce": 64}):
        failures.append(f"unexpected_enabled_losses:{dict(loss_counts)}")

    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "failures": failures,
        "source_stage9699_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "repaired_manifest": str(REPAIRED_MANIFEST.relative_to(ROOT)),
        "row_count": len(repaired),
        "source_split_label_counts": source_counts,
        "repaired_split_label_counts": repaired_counts,
        "missing_labels_by_split": missing_by_split,
        "split_sizes": dict(actual_split_sizes),
        "moved_rows": moved_rows,
        "loss_counts": dict(loss_counts),
        "authority_violations": violations,
        "row_identity_preserved": source_row_ids == repaired_row_ids,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Run Stage9701 contract-only preflight on the Stage9700 rebalanced symbol-binding manifest, including "
        "single-feature shortcut baselines and a native grouped-ablation telemetry design; do not execute target-100M yet."
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "repaired_manifest": str(REPAIRED_MANIFEST.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "metrics": {
            "row_count": len(repaired),
            "split_sizes": dict(actual_split_sizes),
            "moved_rows": moved_rows,
            "missing_labels_by_split": missing_by_split,
            "loss_counts": dict(loss_counts),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9700 Symbol-Binding Repair Compiler",
                "",
                "Stage9700 recompiles the source-backed symbol-binding tiny manifest after Stage9699 diagnosed split coverage gaps and call-label collapse.",
                "",
                "## Repair",
                "",
                "- Preserves all 64 row IDs.",
                "- Reassigns splits to keep the 32/16/16 cap.",
                "- Ensures every binding label appears in train, eval, and strict_eval.",
                "- Leaves decoder CE, runtime, Gemma, harness, and promotion closed.",
                "",
                "## Result",
                "",
                f"- Passed: `{not failures}`",
                f"- Moved rows: `{moved_rows}`",
                f"- Split sizes: `{dict(actual_split_sizes)}`",
                f"- Missing labels by split: `{missing_by_split}`",
                "",
                "## Next",
                "",
                next_step,
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
