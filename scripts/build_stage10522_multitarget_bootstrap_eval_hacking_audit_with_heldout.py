#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10522
NAME = "stage10522_multitarget_bootstrap_eval_hacking_audit_with_heldout"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "multitarget_bootstrap_eval_hacking_audit_with_heldout.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

MANIFEST = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/split_aware_multitarget_bootstrap_manifest_with_heldout.json"
ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/multitarget_bootstrap_with_heldout_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def contains_target_verbatim(row: dict[str, Any]) -> bool:
    input_text = str(row.get("input_text", ""))
    target_text = str(row.get("target_text", "")).strip()
    if not input_text or not target_text or len(target_text) < 8:
        return False
    return target_text in input_text


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    manifest = load_json(MANIFEST)
    rows = load_jsonl(ROWS)

    train_rows = [row for row in rows if row["split_component"] in {"train_bootstrap_bounded", "train_bootstrap_geometry", "train_bootstrap_long_context", "train_teacher_long_context"}]
    validation_rows = [row for row in rows if row["split_component"].startswith("validation_")]
    strict_rows = [row for row in rows if row["split_component"] == "strict_eval_long_context_heldout"]
    reference_rows = [row for row in rows if row["split_component"] == "reference_bounded_eval"]

    strict_verbatim = [row for row in strict_rows if contains_target_verbatim(row)]
    multilingual_strict_languages = Counter(row["language_family"] for row in strict_rows)
    multilingual_headline_ready = all(multilingual_strict_languages.get(lang, 0) > 0 for lang in ("python", "rust", "c_cpp", "web_js_ts_html"))

    failures: list[str] = []
    if manifest["root_split_audit"]["violation_count"] != 0:
        failures.append("root_split_violation_present")
    if not multilingual_headline_ready:
        failures.append("multilingual_strict_coverage_incomplete")
    if strict_verbatim:
        failures.append("strict_rows_have_verbatim_targets")

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(failures) == 0,
        "failures": failures,
        "claim_boundary": [
            "This audit applies to the heldout-aware bootstrap manifest, not the older train-only bootstrap package.",
            "Strict long-context rows are evaluation-safe only for the retained target subtypes decisive_evidence and retrieve_answer_abstain.",
            "Legacy bounded reference rows remain canary-only and should not be merged into multilingual heldout headline metrics.",
        ],
        "global_findings": {
            "root_split_violation_count": manifest["root_split_audit"]["violation_count"],
            "training_rows_total": len(train_rows),
            "validation_rows_total": len(validation_rows),
            "strict_rows_total": len(strict_rows),
            "reference_rows_total": len(reference_rows),
            "strict_verbatim_target_rows_total": len(strict_verbatim),
            "multilingual_headline_ready": multilingual_headline_ready,
        },
        "strict_eval_profile": {
            "strict_languages": dict(sorted(multilingual_strict_languages.items())),
            "strict_target_subtypes": dict(sorted(Counter(row["target_subtype"] for row in strict_rows).items())),
            "strict_repo_counts": dict(sorted(Counter(row["repo_id"] for row in strict_rows).items())),
            "strict_split_role": "heldout_long_context_eval_safe",
        },
        "remaining_truthful_limits": [
            "Strict heldout rows currently cover only decisive_evidence and retrieve_answer_abstain, not full verifier_outcome or patch-sketch generation.",
            "Rust strict heldout depth is still shallow compared with Python.",
            "Web strict heldout currently comes from a single repo family.",
            "This is still a bootstrap curriculum/eval package, not yet the full expert-maintainer benchmark endpoint.",
        ],
        "next_best_step": (
            "Retarget the bootstrap probe request to this heldout-aware manifest, then score the resulting model against Gemma on the 36 strict eval-safe rows. "
            "After that, deepen Rust and web heldout supply and add non-leaky verifier-style rows."
        ),
    }
    write_json(AUDIT_JSON, audit)
    write_json(SUMMARY_JSON, audit)


if __name__ == "__main__":
    main()
