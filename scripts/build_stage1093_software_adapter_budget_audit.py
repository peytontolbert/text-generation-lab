#!/usr/bin/env python3
"""Audit the counted budget of the Stage1092 symbolic software adapter."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _selector_budget(train_rows: list[dict[str, Any]]) -> dict[str, Any]:
    class_counts: Counter[str] = Counter()
    token_counts: dict[str, Counter[str]] = defaultdict(Counter)
    vocab: set[str] = set()
    for row in train_rows:
        proof = row.get("proof_units", {}) or {}
        operator = str(proof.get("operator", ""))
        text = f"{proof.get('contract', '')} {proof.get('invariant', '')}"
        class_counts[operator] += 1
        for token in _tokenize(text):
            token_counts[operator][token] += 1
            vocab.add(token)
    nonzero_token_counts = sum(len(counter) for counter in token_counts.values())
    return {
        "classes": sorted(class_counts),
        "class_count_entries": len(class_counts),
        "vocab_size": len(vocab),
        "nonzero_class_token_count_entries": nonzero_token_counts,
        "counted_selector_scalar_entries": len(class_counts) + nonzero_token_counts,
    }


def _template_budget(template_rows: list[dict[str, Any]]) -> dict[str, Any]:
    body_chars = sum(len(str(row.get("body", ""))) for row in template_rows)
    full_template_chars = sum(len(json.dumps(row, sort_keys=True)) for row in template_rows)
    return {
        "template_count": len(template_rows),
        "template_body_chars": body_chars,
        "template_json_chars": full_template_chars,
        "counted_template_char_entries": body_chars,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("runs/local/artifacts/stage1091_scaled_software_operator_curriculum/manifest.json"))
    parser.add_argument("--templates-jsonl", type=Path, default=Path("runs/local/artifacts/stage1092_operator_template_materialization/induced_templates.jsonl"))
    parser.add_argument("--stage1092-summary", type=Path, default=Path("runs/local/artifacts/stage1092_operator_template_materialization_summary.json"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1093_software_adapter_budget_audit_summary.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    train_rows = _iter_jsonl(Path(manifest["train_path"]))
    eval_rows = _iter_jsonl(Path(manifest["eval_path"]))
    hidden_rows = _iter_jsonl(Path(manifest["hidden_path"]))
    template_rows = _iter_jsonl(args.templates_jsonl)
    stage1092 = json.loads(args.stage1092_summary.read_text(encoding="utf-8"))
    selector = _selector_budget(train_rows)
    templates = _template_budget(template_rows)

    eval_bits = int(stage1092["results"]["eval"]["verified_decision_bits"])
    hidden_bits = int(stage1092["results"]["hidden"]["verified_decision_bits"])
    counted_scalar_plus_char_entries = int(selector["counted_selector_scalar_entries"]) + int(templates["counted_template_char_entries"])
    hidden_bits_per_counted_entry = hidden_bits / counted_scalar_plus_char_entries if counted_scalar_plus_char_entries else 0.0
    eval_bits_per_counted_entry = eval_bits / counted_scalar_plus_char_entries if counted_scalar_plus_char_entries else 0.0
    serious_hidden_bits = 10_000_000
    controlled_hidden_bits = 1_000_000
    pilot_hidden_bits = 100_000
    summary = {
        "artifact_kind": "stage1093_software_adapter_budget_audit",
        "status": "completed_symbolic_adapter_budget_audit",
        "manifest": str(args.manifest),
        "stage1092_summary": str(args.stage1092_summary),
        "selector_budget": selector,
        "template_budget": templates,
        "counted_scalar_plus_char_entries": counted_scalar_plus_char_entries,
        "verified_bits": {
            "eval": eval_bits,
            "hidden": hidden_bits,
            "eval_rows": len(eval_rows),
            "hidden_rows": len(hidden_rows),
        },
        "density": {
            "eval_bits_per_counted_entry": eval_bits_per_counted_entry,
            "hidden_bits_per_counted_entry": hidden_bits_per_counted_entry,
        },
        "scale_targets": {
            "pilot_hidden_verified_bits": pilot_hidden_bits,
            "controlled_claim_hidden_verified_bits": controlled_hidden_bits,
            "serious_claim_hidden_verified_bits": serious_hidden_bits,
            "hidden_rows_needed_at_8_bits_each": {
                "pilot": pilot_hidden_bits // 8,
                "controlled": controlled_hidden_bits // 8,
                "serious": serious_hidden_bits // 8,
            },
        },
        "decision": (
            "Stage1092 has perfect hidden behavior on a tiny split, but the counted adapter density is measured over only 64 hidden bits. "
            "This is far below the pilot/control/serious software-KBPP scale gates; next work should scale hidden verified bits before making any 7B claim."
        ),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
