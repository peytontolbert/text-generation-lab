#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9636
NAME = "stage9636_counterbalanced_observe_probe_failure_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9635_counterbalanced_observe_continuation_tiny_probe.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9635_counterbalanced_observe_continuation_tiny_probe/episode_step_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "counterbalanced_observe_probe_failure_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COUNTERBALANCED_OBSERVE_PROBE_FAILURE_AUDIT_STAGE9636.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def update_registry(summary: dict[str, Any]) -> None:
    registry=load_json(REGISTRY) or {"rows":[],"metrics":{}}
    rows=[row for row in registry.get("rows",[]) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage":STAGE,"stage_name":NAME,"passed":summary["passed"],"path":str(SUMMARY),"authority":dict(AUTHORITY_CLOSED),"next_best_step":summary["next_best_step"]})
    registry["rows"]=sorted(rows,key=lambda row:(int(row.get("stage",-1)),row.get("stage_name","")))
    registry["passed"]=bool(registry["rows"])
    registry["metrics"]={**(registry.get("metrics") or {}),"latest_stage":STAGE,"latest_stage_name":NAME,"latest_stage_next_best_step":summary["next_best_step"],"max_stage":STAGE,"registry_rows":len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source=load_json(SOURCE_SUMMARY)
    rows=load_jsonl(RUN_DIR / "row_field_logits.jsonl")
    failures=[]
    if source.get("metrics",{}).get("safety_passed") is not True:
        failures.append("stage9635_safety_not_passed")
    wrong=[row for row in rows if row.get("correct") is False]
    high=[row for row in wrong if row.get("high_confidence_wrong")]
    counternegative_wrong=[row for row in wrong if str(row.get("row_id","")).startswith("stage9634_counternegative")]
    wrong_by_field=Counter(str(row.get("field")) for row in wrong)
    counternegative_wrong_by_field=Counter(str(row.get("field")) for row in counternegative_wrong)
    pred_pairs=Counter(f"{row.get('field')}::{row.get('target')}=>{row.get('pred')}" for row in counternegative_wrong)
    audit={
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "stage9635_quality_passed": source.get("metrics",{}).get("quality_passed"),
        "stage9635_strict_joint_proxy_exact": source.get("metrics",{}).get("strict_joint_proxy_exact"),
        "wrong_rows": len(wrong),
        "high_confidence_wrong_rows": len(high),
        "counternegative_wrong_rows": len(counternegative_wrong),
        "wrong_by_field": dict(sorted(wrong_by_field.items())),
        "counternegative_wrong_by_field": dict(sorted(counternegative_wrong_by_field.items())),
        "counternegative_top_pred_pairs": dict(pred_pairs.most_common(20)),
        "diagnosis": "The model over-accepts counternegative observe rows, predicting boundary/target true and verified/none with high confidence. The next data patch must upsample same-feature negative observations and separate boundary-token mismatch from verified target text before rerunning.",
        "blocked_execution_next": True,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    next_step="Build Stage9637 counternegative upsample manifest with same source/guard/length buckets but different boundary/target labels; run shortcut audit before another tiny probe."
    summary={"stage":STAGE,"stage_name":NAME,"name":NAME,"passed":audit["passed"],"authority":dict(AUTHORITY_CLOSED),"metrics":{**dict(AUTHORITY_CLOSED),**audit},"artifacts":{"audit":str(AUDIT.relative_to(ROOT)),"doc":str(DOC.relative_to(ROOT))},"decision":"Stage9635 is safe but not quality-passing; do not use the episode-step head as a routing gate yet.","next_best_step":next_step,"created_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9636 Counterbalanced Observe Probe Failure Audit","",f"Passed: `{audit['passed']}`",f"Stage9635 quality passed: `{audit['stage9635_quality_passed']}`",f"Strict joint proxy exact: `{audit['stage9635_strict_joint_proxy_exact']}`",f"High-confidence wrong rows: `{audit['high_confidence_wrong_rows']}`",f"Counternegative wrong rows: `{audit['counternegative_wrong_rows']}`",f"Counternegative wrong by field: `{audit['counternegative_wrong_by_field']}`","",audit["diagnosis"],"",f"Next: {next_step}",""]),encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage":STAGE,"passed":audit["passed"],"next_best_step":next_step,"counternegative_wrong_by_field":audit["counternegative_wrong_by_field"]},indent=2,sort_keys=True))
    if failures: raise SystemExit(1)

if __name__ == "__main__": main()
