#!/usr/bin/env python3
"""Build a debiased review package from mined Python verifier candidates.

Stage11144 found root-disjoint verifier rows, but every mined row used target
label A.  This stage rewrites candidate option order with deterministic
per-row shuffling and emits review-only rows plus anti-cheat metrics.  It does
not merge rows into train support.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11145_fresh_python_verifier_debiased_review_package"
SOURCE_QUEUE = (
    ROOT
    / "runs/local/artifacts/stage11144_fresh_python_verifier_candidate_miner/accepted_python_verifier_candidates.jsonl"
)

LABELS = list("ABCDEFGHJKLMNOPQRSTUVWXYZ")
ROLE_WORDS = {
    "DIRECT_VERIFIER_TARGET",
    "SIBLING_TEST_DISTRACTOR",
    "OTHER_CONSTRAINT_DISTRACTOR",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def find_original_row(candidate: dict[str, Any]) -> dict[str, Any] | None:
    source = ROOT / candidate["source_artifact"]
    row_id = candidate.get("row_id")
    if not source.exists() or not row_id:
        return None
    with source.open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("row_id") == row_id:
                return row
    return None


def shuffled_options(row_id: str, options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keyed = []
    for idx, opt in enumerate(options):
        value = str(opt.get("value", ""))
        digest = hashlib.sha256(f"{row_id}::{idx}::{value}".encode()).hexdigest()
        keyed.append((digest, opt))
    out = []
    for label, (_, opt) in zip(LABELS, sorted(keyed)):
        out.append({"label": label, "value": opt.get("value")})
    return out


def rewrite_prompt_options(prompt: str, options: list[dict[str, Any]]) -> str:
    marker = "\nOptions:\n"
    answer = "\nAnswer:"
    if marker not in prompt or answer not in prompt:
        return prompt
    before = prompt.split(marker, 1)[0]
    after = prompt.split(answer, 1)[1]
    option_text = "\n".join(f"{opt['label']}. {opt['value']}" for opt in options)
    return f"{before}{marker}{option_text}{answer}{after}"


def prompt_leak_flags(prompt: str, target_value: str) -> list[str]:
    flags: list[str] = []
    before_options = prompt.split("\nOptions:\n", 1)[0]
    if "TODO_" in prompt or "PLACEHOLDER" in prompt:
        flags.append("placeholder_text")
    # The verifier target may appear in evidence legitimately, but exact
    # target-only repetition without other verifier choices is suspicious.
    if target_value and target_value in before_options:
        flags.append("target_value_visible_before_options")
    for role in ROLE_WORDS:
        if role in prompt:
            flags.append("semantic_role_word_visible")
            break
    return flags


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = read_jsonl(SOURCE_QUEUE)
    rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    target_labels = Counter()
    source_roots = Counter()
    leak_flags = Counter()

    for cand in candidates:
        original = find_original_row(cand)
        if original is None:
            blocked.append({"candidate": cand, "blocker": "original_row_not_found"})
            continue
        options = original.get("opaque_options")
        if not isinstance(options, list) or len(options) < 3:
            blocked.append({"candidate": cand, "blocker": "insufficient_options"})
            continue
        old_target = str(original.get("target_text") or "")
        target_values = [
            opt.get("value")
            for opt in options
            if isinstance(opt, dict) and str(opt.get("label")) == old_target
        ]
        if not target_values:
            blocked.append({"candidate": cand, "blocker": "target_label_not_in_options"})
            continue
        target_value = str(target_values[0])
        new_row = dict(original)
        new_row_id = f"stage11145::{original.get('row_id')}::debiased_option_order"
        new_options = shuffled_options(new_row_id, options)
        new_target = next(
            opt["label"] for opt in new_options if str(opt.get("value")) == target_value
        )
        prompt = str(original.get("input_text") or original.get("prompt_text") or "")
        new_prompt = rewrite_prompt_options(prompt, new_options)
        flags = prompt_leak_flags(new_prompt, target_value)
        leak_flags.update(flags)

        new_row.update(
            {
                "row_id": new_row_id,
                "input_text": new_prompt,
                "prompt_text": new_prompt,
                "opaque_options": new_options,
                "target_text": new_target,
                "decoder_text": new_target,
                "target_token_len": len(str(new_target).split()),
                "split": "train",
                "split_role": "review_queue_only",
                "train_support_only": True,
                "strict_eval_eligible": False,
                "support_package_stage": 11145,
                "anti_cheat": {
                    **(original.get("anti_cheat") if isinstance(original.get("anti_cheat"), dict) else {}),
                    "deterministic_option_shuffle": True,
                    "stage11145_review_only": True,
                    "source_root_disjoint_from_stage11131": True,
                    "not_merged_into_train": True,
                    "prompt_leak_flags": flags,
                },
                "standalone_projection_source": {
                    "source_artifact": cand["source_artifact"],
                    "source_row_id": original.get("row_id"),
                    "old_target_label": old_target,
                    "target_value": target_value,
                    "projection_mode": "stage11145_deterministic_option_debias_review",
                },
            }
        )
        rows.append(new_row)
        target_labels.update([new_target])
        source_roots.update([str(cand.get("source_root_id"))])

    summary = {
        "stage": 11145,
        "stage_name": "fresh_python_verifier_debiased_review_package",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "candidate_queue": str(SOURCE_QUEUE.relative_to(ROOT)),
        },
        "metrics": {
            "candidate_rows_in": len(candidates),
            "review_rows_out": len(rows),
            "blocked_rows": len(blocked),
            "unique_source_roots": len(source_roots),
            "target_label_counts_after_shuffle": dict(sorted(target_labels.items())),
            "prompt_leak_flag_counts": dict(sorted(leak_flags.items())),
            "source_root_top20": dict(source_roots.most_common(20)),
        },
        "decision": "review_only_not_train_ready",
        "readiness": {
            "label_a_bias_removed": len(target_labels) > 1 and target_labels.get("A", 0) < len(rows),
            "has_prompt_target_visibility_risk": bool(leak_flags),
            "requires_ai_or_human_review": True,
        },
        "next_best_step": (
            "Review these debiased rows for true verifier-transition semantics. "
            "Rows with only broad changed-file/test-list evidence should remain "
            "support-only or be rejected; do not run training until accepted."
        ),
        "outputs": {
            "review_rows_jsonl": str((OUT_DIR / "debiased_python_verifier_review_rows.jsonl").relative_to(ROOT)),
            "blocked_rows_jsonl": str((OUT_DIR / "blocked_python_verifier_candidates.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "fresh_python_verifier_debiased_review_package.json").relative_to(ROOT)),
        },
    }
    with (OUT_DIR / "debiased_python_verifier_review_rows.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    with (OUT_DIR / "blocked_python_verifier_candidates.jsonl").open("w") as f:
        for row in blocked:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    (OUT_DIR / "fresh_python_verifier_debiased_review_package.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
