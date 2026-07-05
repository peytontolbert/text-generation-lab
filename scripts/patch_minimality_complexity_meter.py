from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

HUNK_RE = re.compile(r"^@@")
FILE_RE = re.compile(r"^(?:diff --git|\+\+\+ |--- )")
ADDED_RE = re.compile(r"^\+(?!\+\+ )")
REMOVED_RE = re.compile(r"^-(?!-- )")
PUBLIC_DEF_RE = re.compile(r"^[+-]\s*(def|class)\s+([A-Za-z_]\w*)")
COMPLEXITY_KEYWORDS = (" if ", " for ", " while ", " and ", " or ", " except", " elif ", " with ", " match ", " case ")
DEPENDENCY_PATTERNS = (
    re.compile(r"^[+]\s*import\s+\w+"),
    re.compile(r"^[+]\s*from\s+\w+\s+import\s+"),
    re.compile(r"^[+]\s*[^#\n]*(requirements|pyproject|setup\.py|package\.json|Pipfile|poetry\.lock)"),
)


def patch_text(row: dict[str, Any]) -> str:
    for key in ["patch", "diff", "unified_diff", "patch_text", "candidate_patch"]:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def changed_files_from_patch(text: str) -> set[str]:
    files: set[str] = set()
    for line in text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.add(parts[2].removeprefix("a/"))
                files.add(parts[3].removeprefix("b/"))
        elif line.startswith("+++ ") or line.startswith("--- "):
            path = line[4:].strip().removeprefix("a/").removeprefix("b/")
            if path and path != "/dev/null":
                files.add(path)
    return {f for f in files if f and not f.startswith("/dev/null")}


def line_counts(text: str) -> dict[str, int]:
    added = removed = hunks = 0
    for line in text.splitlines():
        if HUNK_RE.match(line):
            hunks += 1
        if ADDED_RE.match(line):
            added += 1
        elif REMOVED_RE.match(line):
            removed += 1
    return {"added_lines": added, "removed_lines": removed, "changed_lines": added + removed, "hunks": hunks}


def complexity_delta(text: str) -> int:
    delta = 0
    for line in text.splitlines():
        if not (ADDED_RE.match(line) or REMOVED_RE.match(line)):
            continue
        sign = 1 if line.startswith("+") else -1
        padded = f" {line[1:].strip()} "
        delta += sign * sum(padded.count(keyword) for keyword in COMPLEXITY_KEYWORDS)
    return delta


def public_api_touches(text: str) -> list[str]:
    touches: list[str] = []
    for line in text.splitlines():
        m = PUBLIC_DEF_RE.match(line)
        if not m:
            continue
        name = m.group(2)
        if not name.startswith("_"):
            touches.append(f"{m.group(1)}:{name}")
    return sorted(set(touches))


def new_dependency_lines(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        if any(pattern.search(line) for pattern in DEPENDENCY_PATTERNS):
            lines.append(line)
    return lines


def score_patch(row: dict[str, Any], *, max_changed_lines: int = 80, max_files_changed: int = 3, max_complexity_delta: int = 4) -> dict[str, Any]:
    text = patch_text(row)
    counts = line_counts(text)
    files = changed_files_from_patch(text)
    public_touches = public_api_touches(text)
    deps = new_dependency_lines(text)
    cdelta = complexity_delta(text)
    reasons: list[str] = []
    if not text.strip():
        reasons.append("missing_patch_text")
    if counts["changed_lines"] > max_changed_lines:
        reasons.append("changed_lines_over_budget")
    if len(files) > max_files_changed:
        reasons.append("files_changed_over_budget")
    if cdelta > max_complexity_delta:
        reasons.append("complexity_delta_over_budget")
    if public_touches:
        reasons.append("public_api_touch")
    if deps:
        reasons.append("new_dependency_or_import")
    if "missing_patch_text" in reasons:
        route = "HOLD_PATCH_REVIEW"
    elif any(reason.endswith("over_budget") for reason in reasons) or "new_dependency_or_import" in reasons:
        route = "BLOCK_OVERBROAD_PATCH"
    elif public_touches:
        route = "HOLD_PUBLIC_API_REVIEW"
    else:
        route = "PASS_PATCH_MINIMALITY"
    minimality_score = max(0.0, 1.0 - (counts["changed_lines"] / max(max_changed_lines, 1)) - (max(0, len(files) - 1) * 0.1) - max(0, cdelta) * 0.03 - len(public_touches) * 0.08 - len(deps) * 0.1)
    return {
        "row_id": str(row.get("row_id") or row.get("candidate_id") or row.get("id") or "unknown_row"),
        "patch_minimality_route": route,
        "blocked": route == "BLOCK_OVERBROAD_PATCH",
        "needs_review": route in {"HOLD_PATCH_REVIEW", "HOLD_PUBLIC_API_REVIEW"},
        "files_changed": len(files),
        "changed_files": sorted(files),
        "added_lines": counts["added_lines"],
        "removed_lines": counts["removed_lines"],
        "changed_lines": counts["changed_lines"],
        "hunks": counts["hunks"],
        "complexity_delta": cdelta,
        "public_api_touches": public_touches,
        "new_dependency_lines": deps,
        "minimality_score": round(minimality_score, 4),
        "reasons": reasons,
    }


def score_rows(rows: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    records = [score_patch(row, **kwargs) for row in rows]
    route_counts: dict[str, int] = {}
    for record in records:
        route_counts[record["patch_minimality_route"]] = route_counts.get(record["patch_minimality_route"], 0) + 1
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "blocked_rows": sum(int(record["blocked"]) for record in records),
            "review_rows": sum(int(record["needs_review"]) for record in records),
            "pass_rows": sum(int(record["patch_minimality_route"] == "PASS_PATCH_MINIMALITY") for record in records),
            "route_counts": route_counts,
            "avg_minimality_score": round(sum(record["minimality_score"] for record in records) / len(records), 4) if records else 0.0,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Score candidate patches for minimality, complexity, public API touches, and dependency risk.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-changed-lines", type=int, default=80)
    parser.add_argument("--max-files-changed", type=int, default=3)
    parser.add_argument("--max-complexity-delta", type=int, default=4)
    args = parser.parse_args()
    card = score_rows(read_jsonl(args.manifest), max_changed_lines=args.max_changed_lines, max_files_changed=args.max_files_changed, max_complexity_delta=args.max_complexity_delta)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
