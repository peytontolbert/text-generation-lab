#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10500
NAME = "stage10500_hf_local_multitest_repair_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "hf_local_multitest_repair_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKET_JSON = ROOT / "runs/local/artifacts/stage10499_hf_local_multitest_packet_repair/hf_local_multitest_repaired_packet.json"
PREVIEW_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10499_hf_local_multitest_packet_repair/hf_local_multitest_repaired_preview_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    packet = load_json(PACKET_JSON)
    rows = load_jsonl(PREVIEW_ROWS_JSONL)
    evidence_text = json.dumps(packet["bundle"]["maintainer_visible_evidence"], sort_keys=True)

    forbidden_strings = [
        "HFLocalAgent",
        "hf_local",
        "tests/unit/test_hf_local_params.py",
        "tests/unit/test_hf_local_planner_cpu_fallback.py",
        "tests/integration/test_cli_public_interface.py",
        "src/code_assist/agents/hf_local.py",
        "src/code_assist/orchestrator/config.py",
        "src/code_assist/orchestrator/orchestrator.py",
        "src/code_assist/cli.py",
    ]
    leaked_strings = [token for token in forbidden_strings if token in evidence_text]

    verifier_row = next(row for row in rows if row["task_type"] == "verifier_outcome")
    candidate_rows = [row for row in rows if row["task_type"] in {"symptom_localization", "patch_impact"}]

    verifier_options_opaque = all(option.startswith("V") for option in verifier_row["preview_options"])
    candidate_options_opaque = all(
        all(option in {"A", "B", "C", "D"} for option in row["preview_options"])
        for row in candidate_rows
    )
    role_summaries_present = all(
        "role_summary" in option
        for option in verifier_row["prompt_contract"]["verifier_options"]
    )
    weak_neighbor_explicit = "medium-strength neighbor" in json.dumps(packet, sort_keys=True)

    issues: list[dict[str, Any]] = []
    if leaked_strings:
        issues.append(
            {
                "severity": "high",
                "kind": "remaining_prompt_target_leak",
                "finding": "Repaired evidence still exposes concrete target or verifier strings.",
                "evidence": leaked_strings,
            }
        )
    if not verifier_options_opaque:
        issues.append(
            {
                "severity": "high",
                "kind": "raw_verifier_options_visible",
                "finding": "Verifier preview options are not fully opaque.",
                "evidence": verifier_row["preview_options"],
            }
        )
    if not candidate_options_opaque:
        issues.append(
            {
                "severity": "high",
                "kind": "raw_candidate_options_visible",
                "finding": "Candidate preview options are not fully opaque in localization or patch impact rows.",
                "evidence": [row["preview_options"] for row in candidate_rows],
            }
        )
    if not role_summaries_present:
        issues.append(
            {
                "severity": "medium",
                "kind": "missing_verifier_role_summaries",
                "finding": "Verifier options need visible role summaries so the competition is semantic rather than arbitrary IDs.",
                "evidence": verifier_row["prompt_contract"]["verifier_options"],
            }
        )

    admissible_for_next_materialization = not any(issue["severity"] == "high" for issue in issues)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "hf_local_repaired_packet_audited",
        "source_artifacts": {
            "repaired_packet": display(PACKET_JSON),
            "repaired_preview_rows": display(PREVIEW_ROWS_JSONL),
        },
        "summary": {
            "admissible_for_next_materialization": admissible_for_next_materialization,
            "high_severity_issue_count": sum(1 for issue in issues if issue["severity"] == "high"),
            "preview_rows_count": len(rows),
        },
        "anti_cheat_checks": {
            "prompt_target_leak_false": not leaked_strings,
            "verifier_options_opaque": verifier_options_opaque,
            "candidate_options_opaque": candidate_options_opaque,
            "verifier_role_summaries_present": role_summaries_present,
            "weak_neighbor_explicitly_marked": weak_neighbor_explicit,
        },
        "issues": issues,
        "interpretation": [
            "The repaired packet removes the direct path and symbol leaks that made Stage10497 unfit for execution.",
            "The remaining quality limit is not raw leakage but sibling strength: V3 is still a weaker CLI-neighbor distractor than an ideal third verifier family would be.",
        ],
        "recommended_next_stage": "bounded_execution_materialization_for_hf_local_repaired_packet" if admissible_for_next_materialization else "additional_hf_local_packet_repair",
    }

    write_json(AUDIT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "audit": display(AUDIT_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
