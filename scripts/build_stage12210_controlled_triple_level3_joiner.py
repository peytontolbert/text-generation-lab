#!/usr/bin/env python3
"""Wrap complete baseline/mutant/restored verifier triples as Level-3 FAIL_TO_PASS records.

Only admits complete triples with baseline rc=0, mutant rc!=0, restored rc=0.
No command execution, no training.
"""
from __future__ import annotations

import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12210_controlled_triple_level3_joiner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
INCLUDE_STAGE_PARTS = [
    "stage11977_fail_to_pass_mutation_from_pass_roots",
    "stage11978_controlled_fixture_fail_to_pass_materialization",
    "stage11980_controlled_multilingual_fail_to_pass_fixtures",
    "stage11999_real_source_fail_to_pass_mutations",
    "stage12053_controlled_semantic_fail_to_pass_floor_closure_rows",
    "stage12055_controlled_semantic_fail_to_pass_supplement_rows",
]
EXCLUDE_STAGE_PARTS = [
    "stage12025_controlled_fail_to_pass_expansion_rows",
    "stage12003_cpp_real_source_fail_to_pass_mutations",
]

spec = importlib.util.spec_from_file_location("stage12205", ROOT / "scripts/build_stage12205_authoritative_verifier_log_level3_joiner.py")
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(errors="ignore"))
    except Exception:
        return None


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def phase_from_name(path: Path) -> str | None:
    stem = path.stem.lower()
    for phase in ("baseline", "mutant", "restored"):
        if stem.endswith("_" + phase) or stem == phase or ("_" + phase + "_") in stem:
            return phase
    return None


def group_key(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"_(baseline|mutant|restored)(_[0-9]+)?$", "", stem)
    stem = re.sub(r"_(baseline|mutant|restored)_", "_", stem)
    return str(path.parent / stem)


def command_text(row: dict[str, Any]) -> str:
    cmd = row.get("command_text") or row.get("command") or row.get("cmd")
    if isinstance(cmd, list):
        return " ".join(map(str, cmd))
    return str(cmd or "")


def rc(row: dict[str, Any]) -> int | None:
    for k in ("exit_code", "returncode", "return_code"):
        if k in row:
            try:
                return int(row[k])
            except Exception:
                return None
    return None


def tail(row: dict[str, Any], key: str) -> str:
    return str(row.get(key + "_tail") or row.get(key) or "")


def infer_language(path: Path, cmd: str) -> str:
    text = (str(path) + " " + cmd).lower()
    if "cargo" in text or "rust" in text:
        return "rust"
    if "ctest" in text or "cpp" in text or "c_cpp" in text:
        return "c_cpp"
    if "npm" in text or "node" in text or "web" in text:
        return "web_js_ts_html"
    return "python"


def selected_target_from(row: dict[str, Any], path: Path) -> str:
    cmd = command_text(row)
    if "pytest" in cmd:
        parts = cmd.split()
        tests = [p.strip("'") for p in parts if p.endswith(".py") or ".py::" in p]
        if tests:
            return " ".join(tests)
    if "cargo test" in cmd:
        return "cargo test controlled verifier"
    if "ctest" in cmd:
        return "ctest controlled verifier"
    if "npm" in cmd or "node" in cmd:
        return "web controlled verifier"
    return path.stem


def main() -> int:
    groups: dict[str, dict[str, tuple[Path, dict[str, Any]]]] = defaultdict(dict)
    for path in (ROOT / "runs/local/artifacts").rglob("logs/*.json"):
        s = str(path)
        if not any(part in s for part in INCLUDE_STAGE_PARTS):
            continue
        if any(part in s for part in EXCLUDE_STAGE_PARTS):
            continue
        phase = phase_from_name(path)
        if not phase:
            continue
        row = read_json(path)
        if not isinstance(row, dict):
            continue
        if rc(row) is None:
            continue
        groups[group_key(path)][phase] = (path, row)

    records = []
    blocked = []
    for key, phases in sorted(groups.items()):
        if set(phases) != {"baseline", "mutant", "restored"}:
            blocked.append({"group": key, "blocker": "incomplete_triple", "phases": sorted(phases)})
            continue
        b_path, b = phases["baseline"]
        m_path, m = phases["mutant"]
        r_path, r = phases["restored"]
        if rc(b) != 0 or rc(r) != 0 or rc(m) == 0:
            blocked.append({"group": key, "blocker": "triple_returncodes_not_pass_fail_pass", "baseline": rc(b), "mutant": rc(m), "restored": rc(r)})
            continue
        command = {"baseline": command_text(b), "mutant": command_text(m), "restored": command_text(r)}
        stdout = "\n--- baseline ---\n" + tail(b, "stdout") + "\n--- mutant ---\n" + tail(m, "stdout") + "\n--- restored ---\n" + tail(r, "stdout")
        stderr = "\n--- baseline ---\n" + tail(b, "stderr") + "\n--- mutant ---\n" + tail(m, "stderr") + "\n--- restored ---\n" + tail(r, "stderr")
        lang = infer_language(b_path, command_text(b))
        source_stage = next(part for part in INCLUDE_STAGE_PARTS if part in str(b_path))
        rec = mod.pass_record_common(
            source_stage=STAGE + "::" + source_stage,
            source_path=b_path,
            line_no=1,
            root_id=str(b.get("cwd") or r.get("cwd") or key),
            repo_family=source_stage,
            language=lang,
            command=command,
            cwd=str(b.get("cwd") or r.get("cwd") or ""),
            returncode=1,
            selected_target=selected_target_from(b, b_path),
            stdout_tail=stdout,
            stderr_tail=stderr,
            verifier_transition="FAIL_TO_PASS",
            verifier_status="FAIL_TO_PASS",
            extra={
                "controlled_triple": True,
                "baseline_log": str(b_path.relative_to(ROOT)),
                "mutant_log": str(m_path.relative_to(ROOT)),
                "restored_log": str(r_path.relative_to(ROOT)),
                "baseline_rc": rc(b),
                "mutant_rc": rc(m),
                "restored_rc": rc(r),
            },
        )
        records.append(rec)

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "controlled_triple_level3_records.jsonl", records)
    write_jsonl(OUT / "blocked_triples.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "controlled_triple_fail_to_pass_records_materialized" if records else "blocked_no_complete_triples",
        "level3_episode_count": len(records),
        "blocked_count": len(blocked),
        "language_counts": dict(Counter(r.get("language") for r in records)),
        "source_stage_counts": dict(Counter((r.get("source_stage") or "").split("::")[-1] for r in records)),
        "verifier_transition_counts": dict(Counter(r.get("verifier_transition") for r in records)),
        "strict_eval_eligible": False,
        "train_support_only": True,
        "artifact_paths": {
            "records": str(OUT / "controlled_triple_level3_records.jsonl"),
            "blocked": str(OUT / "blocked_triples.jsonl"),
        },
        "claim_boundary": "Controlled baseline/mutant/restored train-support only; no source-heldout or eval claim.",
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if records else 2

if __name__ == "__main__":
    raise SystemExit(main())
