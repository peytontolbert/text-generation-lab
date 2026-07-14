#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10519
NAME = "stage10519_multitarget_bootstrap_eval_hacking_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "multitarget_bootstrap_eval_hacking_audit.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

BOOTSTRAP_MANIFEST = ROOT / "runs/local/artifacts/stage10517_split_aware_multitarget_bootstrap_manifest/split_aware_multitarget_bootstrap_manifest.json"
BOOTSTRAP_ROWS = ROOT / "runs/local/artifacts/stage10517_split_aware_multitarget_bootstrap_manifest/multitarget_bootstrap_rows.jsonl"


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def contains_target_verbatim(row: dict[str, Any]) -> bool:
    input_text = str(row.get("input_text", ""))
    target_text = str(row.get("target_text", "")).strip()
    if not input_text or not target_text:
        return False
    if len(target_text) < 8:
        return False
    return target_text in input_text


def main() -> None:
    manifest = load_json(BOOTSTRAP_MANIFEST)
    rows = load_jsonl(BOOTSTRAP_ROWS)

    leakage_rows = [row for row in rows if contains_target_verbatim(row)]
    leakage_by_split = Counter(row["split_component"] for row in leakage_rows)
    leakage_by_target_family = Counter(row["target_family"] for row in leakage_rows)
    leakage_by_language = Counter(row["language_family"] for row in leakage_rows)

    reference_rows = [row for row in rows if row["split_component"] == "reference_bounded_eval"]
    validation_rows = [row for row in rows if row["split_component"] == "validation_bootstrap_bounded"]
    train_rows = [row for row in rows if row["split_component"] in {"train_bootstrap_bounded", "train_bootstrap_geometry", "train_bootstrap_long_context", "train_teacher_long_context"}]

    reference_languages = Counter(row["language_family"] for row in reference_rows)
    validation_languages = Counter(row["language_family"] for row in validation_rows)
    train_languages = Counter(row["language_family"] for row in train_rows)

    multilingual_headline_ready = all(
        reference_languages.get(lang, 0) > 0 or validation_languages.get(lang, 0) > 0
        for lang in ("python", "rust", "c_cpp", "web_js_ts_html")
    )

    failures: list[str] = []
    if manifest["root_split_audit"]["violation_count"] != 0:
        failures.append("root_split_violation_present")
    if any(row["split_component"] == "reference_bounded_eval" and row.get("lineage_role") != "legacy_reviewed_eval_reference" for row in rows):
        failures.append("unexpected_reference_split_contents")
    if multilingual_headline_ready is False:
        failures.append("multilingual_heldout_coverage_incomplete")

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(failures) == 0,
        "failures": failures,
        "claim_boundary": [
            "This audit distinguishes training-safe bootstrap supervision from honest multilingual benchmark evidence.",
            "Verbatim target presence in train rows is not automatically invalid when the rows are explicitly training-only long-context teacher states.",
            "Reference and validation slices remain the only rows that can speak to headline evaluation claims.",
        ],
        "global_findings": {
            "root_split_violation_count": manifest["root_split_audit"]["violation_count"],
            "training_rows_total": len(train_rows),
            "reference_rows_total": len(reference_rows),
            "validation_rows_total": len(validation_rows),
            "verbatim_target_visible_rows_total": len(leakage_rows),
            "multilingual_headline_ready": multilingual_headline_ready,
        },
        "leakage_profile": {
            "by_split_component": dict(sorted(leakage_by_split.items())),
            "by_target_family": dict(sorted(leakage_by_target_family.items())),
            "by_language": dict(sorted(leakage_by_language.items())),
            "interpretation": [
                "High verbatim-target visibility is concentrated in long-context training rows, where final repair intent and patch sketch targets are teacher-forced outputs.",
                "Those rows are acceptable for training but must not be repurposed as evaluation rows without rebuilding the prompt/target boundary.",
            ],
        },
        "eval_readiness": {
            "reference_languages": dict(sorted(reference_languages.items())),
            "validation_languages": dict(sorted(validation_languages.items())),
            "train_languages": dict(sorted(train_languages.items())),
            "headline_blockers": [
                "No Python heldout rows in the current bootstrap eval path.",
                "Rust appears only in validation seed rows, not a real strict heldout path.",
                "Web strict reference exists only through legacy reviewed carryover, not fresh long-context heldout roots.",
                "Reference rows are canary/reference only and cannot alone justify a fresh 100M-over-Gemma multilingual claim.",
            ],
        },
        "expert_maintainer_eval_read": {
            "appropriate_now_for": [
                "training bootstrap supervision",
                "regression/canary protection",
                "teacher-state seq2seq curriculum scaling",
            ],
            "not_appropriate_yet_for": [
                "fresh multilingual heldout benchmark headline",
                "expert-maintainer evaluation claim across python/rust/c_cpp/web on disjoint roots",
                "anti-cheat-clean source-heldout same-surface Gemma-12B replacement claim",
            ],
        },
        "next_best_step": (
            "Use stage10518 only as a bootstrap training run. For honest multilingual claims, replenish fresh heldout Python, Rust, and web roots, "
            "then rerun the anti-cheat audit with evaluation-only rows that do not expose target text or final repair intents verbatim."
        ),
    }
    write_json(AUDIT_JSON, audit)
    write_json(SUMMARY_JSON, audit)


if __name__ == "__main__":
    main()
