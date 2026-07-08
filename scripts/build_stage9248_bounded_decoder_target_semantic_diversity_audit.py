#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9248
NAME = "stage9248_bounded_decoder_target_semantic_diversity_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage9244_source_backed_arg_context_balanced_bounded_decoder_tiny_package/source_backed_arg_context_balanced_bounded_decoder_tiny_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "bounded_decoder_target_semantic_diversity_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_TARGET_SEMANTIC_DIVERSITY_AUDIT_STAGE9248.md"

LANGUAGE_WORDS = {
    "python": "python",
    "rust": "rust",
    "cpp": "cpp",
    "web_js_ts_html": "typescript",
}
ARG_ECHO = {
    "ARG_CALL": ("call argument",),
    "ARG_IMPORT": ("import argument",),
    "ARG_LITERAL": ("literal argument",),
    "ARG_NAME": ("identifier argument",),
    "ARG_PATH": ("path argument",),
}
TEMPLATE_PHRASES = (
    "use the verified",
    "use the approved",
    "selected from",
    "selected by",
    "the argument supports",
    "source-backed",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def normalized_target(text: str) -> str:
    value = text.lower().strip()
    value = re.sub(r"^for\s+(python|rust|cpp|typescript),\s*", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def analyze_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first_tokens: Counter[str] = Counter()
    normalized_texts: Counter[str] = Counter()
    all_trigrams: Counter[tuple[str, str, str]] = Counter()
    language_prefix_rows = []
    target_contains_language_rows = []
    arg_echo_rows = []
    template_phrase_rows = []
    split_template_phrase_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()

    for row in rows:
        row_id = str(row.get("row_id"))
        split = str(row.get("split"))
        split_counts[split] += 1
        state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        arg = str(state.get("bounded_argument_type") or "")
        language_family = str(row.get("language_family") or "")
        language_word = LANGUAGE_WORDS.get(language_family, language_family)
        text = str((row.get("target") or {}).get("decoder_text") or "")
        low = text.lower().strip()
        tokens = tokenize(text)
        if tokens:
            first_tokens[tokens[0]] += 1
        normalized_texts[normalized_target(text)] += 1
        all_trigrams.update(ngrams(tokens, 3))
        if low.startswith(f"for {language_word.lower()},"):
            language_prefix_rows.append(row_id)
        if language_word and re.search(rf"\b{re.escape(language_word.lower())}\b", low):
            target_contains_language_rows.append(row_id)
        if any(phrase in low for phrase in ARG_ECHO.get(arg, ())):
            arg_echo_rows.append(row_id)
        phrase_hits = [phrase for phrase in TEMPLATE_PHRASES if phrase in low]
        if phrase_hits:
            template_phrase_rows.append({"row_id": row_id, "phrases": phrase_hits})
            split_template_phrase_counts[split] += 1

    rows_count = len(rows)
    first_token_dominance = max(first_tokens.values(), default=0) / max(rows_count, 1)
    unique_normalized_rate = len(normalized_texts) / max(rows_count, 1)
    unique_trigram_rate = len(all_trigrams) / max(sum(all_trigrams.values()), 1)
    template_phrase_rate = len(template_phrase_rows) / max(rows_count, 1)
    language_prefix_rate = len(language_prefix_rows) / max(rows_count, 1)
    arg_echo_rate = len(arg_echo_rows) / max(rows_count, 1)
    target_contains_language_rate = len(target_contains_language_rows) / max(rows_count, 1)

    checks = {
        "rows_present": rows_count > 0,
        "language_prefix_rows_zero": len(language_prefix_rows) == 0,
        "target_contains_language_rows_zero": len(target_contains_language_rows) == 0,
        "arg_type_echo_rows_zero": len(arg_echo_rows) == 0,
        "template_phrase_rate_le_0_25": template_phrase_rate <= 0.25,
        "first_token_dominance_rate_le_0_50": first_token_dominance <= 0.50,
        "unique_normalized_target_rate_ge_0_80": unique_normalized_rate >= 0.80,
        "unique_trigram_rate_ge_0_20": unique_trigram_rate >= 0.20,
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "rows": rows_count,
        "split_counts": dict(sorted(split_counts.items())),
        "first_token_counts": dict(first_tokens.most_common(10)),
        "first_token_dominance_rate": first_token_dominance,
        "unique_normalized_targets": len(normalized_texts),
        "unique_normalized_target_rate": unique_normalized_rate,
        "unique_trigrams": len(all_trigrams),
        "total_trigrams": sum(all_trigrams.values()),
        "unique_trigram_rate": unique_trigram_rate,
        "language_prefix_rows": len(language_prefix_rows),
        "language_prefix_rate": language_prefix_rate,
        "target_contains_language_rows": len(target_contains_language_rows),
        "target_contains_language_rate": target_contains_language_rate,
        "arg_type_echo_rows": len(arg_echo_rows),
        "arg_type_echo_rate": arg_echo_rate,
        "template_phrase_rows": len(template_phrase_rows),
        "template_phrase_rate": template_phrase_rate,
        "split_template_phrase_counts": dict(sorted(split_template_phrase_counts.items())),
        "examples": {
            "language_prefix_row_ids": language_prefix_rows[:10],
            "target_contains_language_row_ids": target_contains_language_rows[:10],
            "arg_echo_row_ids": arg_echo_rows[:10],
            "template_phrase_rows": template_phrase_rows[:10],
            "top_normalized_targets": normalized_texts.most_common(10),
            "top_trigrams": [(" ".join(k), v) for k, v in all_trigrams.most_common(10)],
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(MANIFEST)
    audit = analyze_rows(rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Stage9244 target text passed semantic diversity checks." if audit["passed"] else "Stage9244 target text is too templated or label-echoed for capability interpretation; do not execute the tiny CE probe until target rendering is repaired.",
        "next_best_step": "Repair the bounded decoder target renderer to produce non-template, non-label-echo, source-backed bounded argument targets, then rerun package/preflight/review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9248 Bounded Decoder Target Semantic Diversity Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Rows: `{audit['rows']}`",
        f"First-token dominance rate: `{audit['first_token_dominance_rate']:.3f}`",
        f"Language-prefix rows: `{audit['language_prefix_rows']}`",
        f"Target contains language rows: `{audit['target_contains_language_rows']}`",
        f"Argument-type echo rows: `{audit['arg_type_echo_rows']}`",
        f"Template phrase rows: `{audit['template_phrase_rows']}`",
        f"Unique normalized target rate: `{audit['unique_normalized_target_rate']:.3f}`",
        f"Unique trigram rate: `{audit['unique_trigram_rate']:.3f}`",
        "",
        "This is a no-execution audit. It does not train or instantiate the model. It checks whether the current bounded decoder targets are meaningful enough for capability interpretation rather than template memorization.",
        "",
        f"Decision: {summary['decision']}",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if audit["passed"] else 1)


if __name__ == "__main__":
    main()
