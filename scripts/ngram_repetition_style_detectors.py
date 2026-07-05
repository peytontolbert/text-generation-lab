from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+|[^\s]")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if n <= 0 or len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def repetition_ratio(tokens: list[str], n: int) -> float:
    grams = ngrams(tokens, n)
    if not grams:
        return 0.0
    counts = Counter(grams)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated / len(grams)


def style_features(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    stripped = [line for line in lines if line.strip()]
    long_lines = [line for line in lines if len(line) > 100]
    indent_widths = []
    trailing_ws = 0
    tab_indents = 0
    for line in lines:
        if line.rstrip() != line:
            trailing_ws += 1
        leading = len(line) - len(line.lstrip(" "))
        if line.startswith("\t"):
            tab_indents += 1
        if leading:
            indent_widths.append(leading)
    odd_indents = [w for w in indent_widths if w % 4 != 0]
    return {
        "line_count": len(lines),
        "nonempty_line_count": len(stripped),
        "long_line_count": len(long_lines),
        "trailing_ws_lines": trailing_ws,
        "tab_indent_lines": tab_indents,
        "odd_indent_lines": len(odd_indents),
        "avg_line_length": round(sum(len(line) for line in lines) / len(lines), 4) if lines else 0.0,
    }


def detect_text(text: str, *, high_repeat_threshold: float = 0.18) -> dict[str, Any]:
    tokens = tokenize(text)
    uni = repetition_ratio(tokens, 1)
    bi = repetition_ratio(tokens, 2)
    tri = repetition_ratio(tokens, 3)
    style = style_features(text)
    reasons: list[str] = []
    if bi >= high_repeat_threshold or tri >= high_repeat_threshold:
        reasons.append("high_ngram_repetition")
    if style["long_line_count"]:
        reasons.append("long_lines")
    if style["odd_indent_lines"] or style["tab_indent_lines"]:
        reasons.append("indent_style_anomaly")
    if style["trailing_ws_lines"]:
        reasons.append("trailing_whitespace")
    if len(tokens) < 3:
        reasons.append("too_few_tokens")
    if "high_ngram_repetition" in reasons:
        route = "HOLD_REPETITION_REVIEW"
    elif reasons:
        route = "PASS_WITH_STYLE_WARNINGS"
    else:
        route = "PASS_STYLE_PRIOR"
    style_risk_score = min(1.0, bi * 2.0 + tri * 3.0 + style["long_line_count"] * 0.05 + style["odd_indent_lines"] * 0.05 + style["trailing_ws_lines"] * 0.03)
    return {
        "token_count": len(tokens),
        "unigram_repetition_ratio": round(uni, 4),
        "bigram_repetition_ratio": round(bi, 4),
        "trigram_repetition_ratio": round(tri, 4),
        "style_features": style,
        "style_risk_score": round(style_risk_score, 4),
        "style_route": route,
        "reasons": reasons,
    }


def row_text(row: dict[str, Any]) -> str:
    for key in ["decoder_text", "target_text", "patch", "code", "text", "candidate", "output_text"]:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def detect_row(row: dict[str, Any]) -> dict[str, Any]:
    features = detect_text(row_text(row))
    return {
        "row_id": str(row.get("row_id") or row.get("candidate_id") or row.get("id") or "unknown_row"),
        **features,
    }


def detect_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    records = [detect_row(row) for row in rows]
    route_counts: dict[str, int] = {}
    for record in records:
        route_counts[record["style_route"]] = route_counts.get(record["style_route"], 0) + 1
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "warning_rows": sum(int(record["style_route"] == "PASS_WITH_STYLE_WARNINGS") for record in records),
            "review_rows": sum(int(record["style_route"] == "HOLD_REPETITION_REVIEW") for record in records),
            "pass_rows": sum(int(record["style_route"] == "PASS_STYLE_PRIOR") for record in records),
            "route_counts": route_counts,
            "avg_style_risk_score": round(sum(record["style_risk_score"] for record in records) / len(records), 4) if records else 0.0,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit n-gram repetition and style-anomaly features for code/text rows.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = detect_rows(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
