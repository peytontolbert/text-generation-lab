from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

PATTERNS = {
    "python_eval_exec": re.compile(r"\b(eval|exec)\s*\("),
    "shell_true": re.compile(r"shell\s*=\s*True"),
    "pickle_load": re.compile(r"\bpickle\.loads?\s*\("),
    "yaml_unsafe_load": re.compile(r"yaml\.load\s*\([^\n)]*(?!Loader\s*=\s*yaml\.SafeLoader)"),
    "sql_string_concat": re.compile(r"SELECT\s+.+\+.+FROM|WHERE\s+.+\+", re.IGNORECASE),
    "hardcoded_secret": re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{8,}['\"]"),
    "insecure_random_token": re.compile(r"random\.(random|randint|choice)\s*\("),
    "debug_true": re.compile(r"DEBUG\s*=\s*True"),
}
HIGH_SEVERITY = {"python_eval_exec", "shell_true", "pickle_load", "yaml_unsafe_load", "hardcoded_secret"}
MEDIUM_SEVERITY = {"sql_string_concat", "insecure_random_token", "debug_true"}


def row_text(row: dict[str, Any]) -> str:
    for key in ["code", "patch", "source", "text", "candidate", "diff"]:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def scan_text(text: str) -> dict[str, Any]:
    findings = []
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            severity = "high" if name in HIGH_SEVERITY else "medium" if name in MEDIUM_SEVERITY else "low"
            findings.append({"rule_id": name, "severity": severity, "line": line_no, "snippet": match.group(0)[:120]})
    high = sum(1 for f in findings if f["severity"] == "high")
    medium = sum(1 for f in findings if f["severity"] == "medium")
    if high:
        route = "BLOCK_SECURITY_RISK"
    elif medium:
        route = "HOLD_SECURITY_REVIEW"
    else:
        route = "PASS_STATIC_SECURITY_SCAN"
    return {"security_route": route, "findings": findings, "high_count": high, "medium_count": medium, "finding_count": len(findings)}


def scan_row(row: dict[str, Any]) -> dict[str, Any]:
    scan = scan_text(row_text(row))
    return {"row_id": str(row.get("row_id") or row.get("candidate_id") or row.get("id") or "unknown_row"), **scan}


def scan_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    records = [scan_row(row) for row in rows]
    route_counts = Counter(record["security_route"] for record in records)
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "pass_rows": route_counts.get("PASS_STATIC_SECURITY_SCAN", 0),
            "review_rows": route_counts.get("HOLD_SECURITY_REVIEW", 0),
            "blocked_rows": route_counts.get("BLOCK_SECURITY_RISK", 0),
            "route_counts": dict(route_counts),
            "finding_count": sum(record["finding_count"] for record in records),
            "high_count": sum(record["high_count"] for record in records),
            "medium_count": sum(record["medium_count"] for record in records),
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Static no-runtime security scanner for code/config rows.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = scan_rows(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
