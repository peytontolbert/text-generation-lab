from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TEST_PATH_MARKERS = ("test_", "_test.py", "/tests/", "tests/")


def norm_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def is_test_path(path: str) -> bool:
    p = norm_path(path)
    name = p.rsplit("/", 1)[-1]
    return p.startswith("tests/") or "/tests/" in p or name.startswith("test_") or name.endswith("_test.py")


def basename_stem(path: str) -> str:
    name = norm_path(path).rsplit("/", 1)[-1]
    if name.endswith(".py"):
        name = name[:-3]
    if name.startswith("test_"):
        name = name[5:]
    if name.endswith("_test"):
        name = name[:-5]
    return name


def candidate_tests_for_change(change: dict[str, Any], repo_index: dict[str, Any]) -> list[dict[str, Any]]:
    changed_path = norm_path(str(change.get("path") or change.get("file") or ""))
    changed_symbol = str(change.get("symbol") or change.get("function") or change.get("class") or "")
    explicit = repo_index.get("coverage_map", {}) if isinstance(repo_index.get("coverage_map"), dict) else {}
    tests = set()
    for key in [changed_path, changed_symbol, f"{changed_path}:{changed_symbol}" if changed_symbol else ""]:
        value = explicit.get(key)
        if isinstance(value, list):
            tests.update(norm_path(str(v)) for v in value)
    all_files = [norm_path(str(p)) for p in repo_index.get("files", [])]
    test_files = [p for p in all_files if is_test_path(p)]
    stem = basename_stem(changed_path)
    symbol_lower = changed_symbol.lower()
    for test in test_files:
        tstem = basename_stem(test)
        if stem and (stem == tstem or stem in tstem or tstem in stem):
            tests.add(test)
        if symbol_lower and symbol_lower in test.lower():
            tests.add(test)
    call_graph = repo_index.get("test_to_symbols", {}) if isinstance(repo_index.get("test_to_symbols"), dict) else {}
    for test, symbols in call_graph.items():
        if changed_symbol and changed_symbol in {str(s) for s in symbols}:
            tests.add(norm_path(str(test)))
    ranked = []
    for test in sorted(tests):
        reason = []
        if explicit.get(changed_path) or explicit.get(changed_symbol):
            reason.append("coverage_map")
        if basename_stem(test) and stem and (stem in basename_stem(test) or basename_stem(test) in stem):
            reason.append("path_stem_match")
        if changed_symbol and (changed_symbol.lower() in test.lower() or changed_symbol in {str(s) for s in call_graph.get(test, [])}):
            reason.append("symbol_match")
        ranked.append({"test_path": test, "reasons": sorted(set(reason)) or ["repo_test_candidate"], "score": len(set(reason)) or 1})
    return sorted(ranked, key=lambda item: (-item["score"], item["test_path"]))


def select_tests(row: dict[str, Any], *, max_tests: int = 8) -> dict[str, Any]:
    repo_index = row.get("repo_index") if isinstance(row.get("repo_index"), dict) else {}
    changes = row.get("changes") if isinstance(row.get("changes"), list) else []
    candidates: dict[str, dict[str, Any]] = {}
    for change in changes:
        if not isinstance(change, dict):
            continue
        for candidate in candidate_tests_for_change(change, repo_index):
            current = candidates.get(candidate["test_path"])
            if current is None or candidate["score"] > current["score"]:
                candidates[candidate["test_path"]] = candidate
    ranked = sorted(candidates.values(), key=lambda item: (-item["score"], item["test_path"]))
    selected = ranked[:max_tests]
    if not changes:
        route = "HOLD_NO_CHANGESET"
    elif not selected:
        route = "NEEDS_BROAD_TEST_DISCOVERY"
    else:
        route = "PASS_TARGETED_TEST_SELECTION"
    return {
        "row_id": str(row.get("row_id") or row.get("candidate_id") or row.get("id") or "unknown_row"),
        "test_selection_route": route,
        "selected_tests": [item["test_path"] for item in selected],
        "candidate_tests": ranked,
        "selected_count": len(selected),
        "change_count": len(changes),
        "coverage_gap": route != "PASS_TARGETED_TEST_SELECTION",
    }


def select_for_rows(rows: list[dict[str, Any]], *, max_tests: int = 8) -> dict[str, Any]:
    records = [select_tests(row, max_tests=max_tests) for row in rows]
    route_counts: dict[str, int] = {}
    for record in records:
        route_counts[record["test_selection_route"]] = route_counts.get(record["test_selection_route"], 0) + 1
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "pass_rows": sum(int(record["test_selection_route"] == "PASS_TARGETED_TEST_SELECTION") for record in records),
            "coverage_gap_rows": sum(int(record["coverage_gap"]) for record in records),
            "route_counts": route_counts,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Select candidate tests for changed files/symbols using static repo/test metadata.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-tests", type=int, default=8)
    args = parser.parse_args()
    card = select_for_rows(read_jsonl(args.manifest), max_tests=args.max_tests)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
