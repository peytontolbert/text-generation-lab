#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10527
NAME = "stage10527_bootstrap_heldout_expert_eval_appropriateness_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "bootstrap_heldout_expert_eval_appropriateness_audit.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

STRICT_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/strict_eval_rows.jsonl"
TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/train_rows.jsonl"
AUDIT_10522 = ROOT / "runs/local/artifacts/stage10522_multitarget_bootstrap_eval_hacking_audit_with_heldout/multitarget_bootstrap_eval_hacking_audit_with_heldout.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
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
    input_text = str(row.get("input_text") or "")
    target_text = str(row.get("target_text") or "").strip()
    if not input_text or not target_text or len(target_text) < 8:
        return False
    return target_text in input_text


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def realism_bucket(row: dict[str, Any]) -> str:
    text = str(row.get("input_text") or "")
    has_file = bool(re.search(r"\b[a-zA-Z0-9_\-/]+\.(py|rs|cpp|cc|c|h|hpp|ts|tsx|js|jsx|html|yaml|yml|toml)\b", text))
    has_symbols = "Key symbols:" in text
    has_changed_files = "Changed files:" in text
    has_verifier = "Verification targets:" in text or "Verifier route:" in text
    has_trace = "Trace:" in text or "Stack:" in text or "Call path:" in text
    has_code = "```" in text or "def " in text or "fn " in text or "#include" in text or "class " in text
    score = sum([has_file, has_symbols, has_changed_files, has_verifier, has_trace, has_code])
    if score >= 5:
        return "L3_plus"
    if score >= 3:
        return "L2"
    if score >= 1:
        return "L1"
    return "L0"


def target_shape(row: dict[str, Any]) -> str:
    target = str(row.get("target_text") or "")
    if target == "ANSWER_WITH_RETRIEVED_EVIDENCE":
        return "retrieve_answer_abstain_constant"
    if target.startswith("[") and target.endswith("]"):
        return "json_array_chunk_ids"
    return "other"


def main() -> None:
    strict_rows = load_jsonl(STRICT_ROWS)
    train_rows = load_jsonl(TRAIN_ROWS)
    prior_audit = load_json(AUDIT_10522) if AUDIT_10522.exists() else {}

    strict_by_root = Counter(str(row.get("root_id") or "") for row in strict_rows)
    train_root_ids = {str(row.get("root_id") or "") for row in train_rows}
    strict_root_overlap = sorted(root_id for root_id in strict_by_root if root_id and root_id in train_root_ids)

    exact_input_counts = Counter(normalize_text(str(row.get("input_text") or "")) for row in strict_rows)
    duplicate_strict_prompts = {text: count for text, count in exact_input_counts.items() if text and count > 1}

    metadata_prompt_target_leak_true = [row for row in strict_rows if ((row.get("anti_cheat") or {}).get("prompt_target_leak")) is True]
    actual_prompt_target_leak_true = [row for row in strict_rows if contains_target_verbatim(row)]
    metadata_drift_rows = [
        str(row.get("row_id") or "")
        for row in strict_rows
        if bool((row.get("anti_cheat") or {}).get("prompt_target_leak")) != contains_target_verbatim(row)
    ]

    by_language = Counter(str(row.get("language_family") or "unknown") for row in strict_rows)
    by_repo = Counter(str(row.get("repo_id") or row.get("repo_family") or "unknown") for row in strict_rows)
    by_subtype = Counter(str(row.get("target_subtype") or "unknown") for row in strict_rows)
    by_realism = Counter(realism_bucket(row) for row in strict_rows)
    by_target_shape = Counter(target_shape(row) for row in strict_rows)

    repo_by_language: dict[str, set[str]] = defaultdict(set)
    for row in strict_rows:
        repo_by_language[str(row.get("language_family") or "unknown")].add(str(row.get("repo_id") or row.get("repo_family") or "unknown"))

    failures: list[str] = []
    warnings: list[str] = []

    if strict_root_overlap:
        failures.append("strict_root_overlap_with_train")
    if actual_prompt_target_leak_true:
        failures.append("actual_prompt_target_leak_present")
    if len(repo_by_language.get("web_js_ts_html", set())) <= 1:
        warnings.append("web_single_repo_family")
    if by_language.get("rust", 0) < 8:
        warnings.append("rust_supply_thin")
    if by_subtype.keys() != {"decisive_evidence", "retrieve_answer_abstain"}:
        warnings.append("unexpected_target_subtypes_present")
    if by_target_shape.get("retrieve_answer_abstain_constant", 0) == by_subtype.get("retrieve_answer_abstain", 0):
        warnings.append("abstain_rows_single_constant_target")
    if by_realism.get("L3_plus", 0) == 0:
        warnings.append("no_high_realism_rows")
    if metadata_drift_rows:
        warnings.append("anti_cheat_metadata_drift")
    if duplicate_strict_prompts:
        warnings.append("duplicate_visible_prompts_present")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
        "claim_scope": [
            "Expert-maintainer appropriateness and eval-hacking audit for the stage10521 bootstrap-heldout strict slice.",
            "This audits visible-surface leakage risk, metadata drift, realism depth, and repo/language concentration.",
            "It does not certify the slice as a full expert-maintainer benchmark endpoint.",
        ],
        "strict_slice_profile": {
            "rows": len(strict_rows),
            "by_language": dict(sorted(by_language.items())),
            "by_repo": dict(sorted(by_repo.items())),
            "by_target_subtype": dict(sorted(by_subtype.items())),
            "repo_count_by_language": {k: len(v) for k, v in sorted(repo_by_language.items())},
            "realism_buckets": dict(sorted(by_realism.items())),
            "target_shapes": dict(sorted(by_target_shape.items())),
        },
        "anti_cheat_audit": {
            "strict_root_overlap_with_train_count": len(strict_root_overlap),
            "strict_root_overlap_with_train": strict_root_overlap,
            "metadata_prompt_target_leak_true_count": len(metadata_prompt_target_leak_true),
            "actual_prompt_target_leak_true_count": len(actual_prompt_target_leak_true),
            "metadata_drift_row_count": len(metadata_drift_rows),
            "metadata_drift_rows": metadata_drift_rows[:20],
            "duplicate_visible_prompt_count": len(duplicate_strict_prompts),
            "duplicate_visible_prompts": [
                {"count": count, "input_text": text}
                for text, count in sorted(duplicate_strict_prompts.items(), key=lambda item: (-item[1], item[0]))[:10]
            ],
            "prior_stage10522": {
                "passed": bool(prior_audit.get("passed")),
                "strict_verbatim_target_rows_total": ((prior_audit.get("global_findings") or {}).get("strict_verbatim_target_rows_total")),
                "multilingual_headline_ready": ((prior_audit.get("global_findings") or {}).get("multilingual_headline_ready")),
            },
        },
        "expert_appropriateness_findings": [
            "The strict slice is suitable as a bootstrap-heldout seq2seq safety/comparison slice, not yet as a full expert-maintainer endpoint.",
            "Visible surfaces are summarized maintainer states rather than full trace-plus-snippet adjudication bundles.",
            "Retrieve/answer/abstain rows currently collapse to a single constant target string, so they should be reported separately from richer generation tasks.",
            "Web strict coverage remains single-repo and should not support broad web maintainer claims yet.",
            "Inherited anti_cheat.prompt_target_leak metadata is stale on all 36 strict rows and must not be interpreted as actual visible-surface leakage.",
        ],
        "next_best_step": (
            "Keep stage10525 as a bootstrap-heldout comparison only, run stage10526 as a canary regression gate, "
            "and for the next manifest expand verifier_outcome and patch-sketch heldout rows with stronger multi-repo Rust and web coverage."
        ),
    }
    write_json(AUDIT_JSON, payload)
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
