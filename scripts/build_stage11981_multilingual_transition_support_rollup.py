#!/usr/bin/env python3
"""Roll up Python source-backed support with controlled multilingual FAIL_TO_PASS fixtures."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11981
NAME = "stage11981_multilingual_transition_support_rollup"
OUT = ART / NAME
SUMMARY = OUT / "multilingual_transition_support_rollup.json"
ROWS = OUT / "multilingual_transition_support_rows.jsonl"
PY_ROWS = ART / "stage11979_transition_review_package_with_fixture_fail_to_pass/transition_review_package_with_fixture_fail_to_pass.jsonl"
MULTI_ROWS = ART / "stage11980_controlled_multilingual_fail_to_pass_fixtures/controlled_multilingual_fail_to_pass_review_rows.jsonl"

FLOOR_STATUS = {"FAIL_TO_PASS": 50, "PASS_TO_PASS": 100, "PASS_CURRENT_BUILD": 40, "PASS_CURRENT_BUILD_AND_RUN": 40, "INSUFFICIENT_EVIDENCE": 40, "NOT_EXERCISED": 40}
FLOOR_LANG = {"python": 50, "rust": 50, "c_cpp": 50, "web_js_ts_html": 50}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    rows=[]
    for row in read_jsonl(PY_ROWS):
        r=dict(row); r["stage11981_supply_source"]="stage11979_python_source_and_fixture_support"; rows.append(r)
    for row in read_jsonl(MULTI_ROWS):
        r=dict(row); r["stage11981_supply_source"]="stage11980_controlled_multilingual_fixture_support"; rows.append(r)
    write_jsonl(ROWS,rows)
    status=Counter(r.get("observed_verifier_transition") for r in rows)
    lang=Counter(r.get("language_family") for r in rows)
    supply=Counter(r.get("stage11981_supply_source") for r in rows)
    artifact={"stage":STAGE,"stage_name":NAME,"created_at_utc":now(),"decision":"multilingual_transition_support_rollup_ready_not_trainable_frontier","source_artifacts":{"stage11979_rows":rel(PY_ROWS),"stage11980_rows":rel(MULTI_ROWS)},"summary":{"rows":len(rows),"status_counts":dict(status),"language_counts":dict(lang),"supply_counts":dict(supply)},"remaining_to_floor":{"status_remaining":{k:max(0,v-status.get(k,0)) for k,v in FLOOR_STATUS.items()},"language_remaining":{k:max(0,v-lang.get(k,0)) for k,v in FLOOR_LANG.items()}},"quality_decision":{"train_package_ready":False,"can_be_used_as_replay_support":True,"reason":["Package now has at least one transition support row for Python, C/C++, Rust, and Web.","C++/Rust/Web FAIL_TO_PASS rows are controlled fixtures, not source-heldout or strict eval evidence.","Total rows remain 19, far below Transition-Root-250 floors.","Fresh Rust real-repo source supply remains unresolved."]},"outputs":{"summary":rel(SUMMARY),"rows":rel(ROWS)},"next_stage_recommendation":{"stage":"stage11982_transition_support_replay_probe_request","action":"Optionally build a tiny replay-only diagnostic from Stage11981, but do not promote unless protected gates are preserved and heldout transition score improves; better next work remains real non-Python source materialization."}}
    write_json(SUMMARY,artifact)
    print(json.dumps({"decision":artifact["decision"],"summary":artifact["summary"],"quality_decision":artifact["quality_decision"],"next":artifact["next_stage_recommendation"]},indent=2,sort_keys=True))

if __name__ == "__main__":
    main()
