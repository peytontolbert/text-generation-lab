#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10498
NAME = "stage10498_hf_local_multitest_verifier_packet_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "hf_local_multitest_verifier_packet_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKET_JSON = ROOT / "runs/local/artifacts/stage10497_hf_local_multitest_verifier_packet_builder/hf_local_multitest_verifier_packet.json"
PREVIEW_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10497_hf_local_multitest_verifier_packet_builder/hf_local_multitest_verifier_preview_rows.jsonl"
REQUEST_JSON = ROOT / "runs/local/artifacts/stage10496_hf_local_verifier_geometry_rebuild_request/hf_local_verifier_geometry_rebuild_request.json"


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


def contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def main() -> None:
    packet = load_json(PACKET_JSON)
    rows = load_jsonl(PREVIEW_ROWS_JSONL)
    request = load_json(REQUEST_JSON)

    evidence = packet["bundle"]["maintainer_visible_evidence"]
    evidence_text = json.dumps(evidence, sort_keys=True)
    selected_tests = packet["bundle"]["selected_tests"]
    gold_verifier = packet["verifier_geometry"]["gold_verifier_candidate"]
    sibling_tests = packet["verifier_geometry"]["tempting_wrong_siblings"]

    explicit_hf_local_mentions = [
        "HFLocalAgent" in json.dumps(entry)
        for group in evidence.values()
        for entry in group
    ]
    gold_test_name_visible_in_evidence = gold_verifier in evidence_text
    sibling_test_names_visible_in_evidence = {
        test: test in evidence_text for test in sibling_tests
    }

    verifier_row = next(row for row in rows if row["task_type"] == "verifier_outcome")
    abstain_row = next(row for row in rows if row["task_type"] == "abstention_insufficient_evidence")

    issues: list[dict[str, Any]] = []

    if gold_test_name_visible_in_evidence:
        issues.append(
            {
                "severity": "high",
                "kind": "prompt_target_leak",
                "finding": "The gold verifier test path is visible in the evidence block before answering.",
                "evidence": gold_verifier,
            }
        )

    if any(explicit_hf_local_mentions):
        issues.append(
            {
                "severity": "high",
                "kind": "symbol_name_shortcut",
                "finding": "The evidence still names HFLocalAgent directly, which risks symbol-name solving instead of verifier disambiguation.",
                "evidence": "HFLocalAgent",
            }
        )

    weak_sibling_tests = []
    for test in sibling_tests:
        if "planner_list" in test or "cli_public_interface" in test:
            weak_sibling_tests.append(test)
    if weak_sibling_tests:
        issues.append(
            {
                "severity": "medium",
                "kind": "weak_sibling_competition",
                "finding": "One sibling verifier target is likely too weak because it checks planner listing rather than hf_local parameter semantics.",
                "evidence": weak_sibling_tests,
            }
        )

    if len(verifier_row["preview_options"]) < request["rebuild_requirements"]["minimum_visible_verifier_targets"]:
        issues.append(
            {
                "severity": "high",
                "kind": "insufficient_verifier_targets",
                "finding": "Verifier row does not meet the minimum visible target count.",
                "evidence": verifier_row["preview_options"],
            }
        )

    if abstain_row["preview_gold_value"] != "ABSTAIN_INSUFFICIENT_EVIDENCE":
        issues.append(
            {
                "severity": "medium",
                "kind": "abstention_contract_mismatch",
                "finding": "Abstention row is not preserving the expected honesty answer.",
                "evidence": abstain_row["preview_gold_value"],
            }
        )

    admissible_now = not any(issue["severity"] == "high" for issue in issues)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "hf_local_multitest_packet_audited",
        "claim_scope": [
            "Audit whether the stage10497 hf_local multi-test verifier packet is clean enough for bounded execution materialization.",
            "Judge both leakage risk and whether the sibling tests create real verifier-target competition rather than decorative extra options.",
        ],
        "source_artifacts": {
            "packet_json": display(PACKET_JSON),
            "preview_rows": display(PREVIEW_ROWS_JSONL),
            "rebuild_request": display(REQUEST_JSON),
        },
        "summary": {
            "selected_tests_count": len(selected_tests),
            "verifier_option_count": len(verifier_row["preview_options"]),
            "admissible_now": admissible_now,
            "high_severity_issue_count": sum(1 for issue in issues if issue["severity"] == "high"),
        },
        "anti_cheat_checks": {
            "gold_test_name_visible_in_evidence": gold_test_name_visible_in_evidence,
            "sibling_test_names_visible_in_evidence": sibling_test_names_visible_in_evidence,
            "explicit_hf_local_symbol_visible": any(explicit_hf_local_mentions),
            "verifier_target_count_gte_3": len(verifier_row["preview_options"]) >= request["rebuild_requirements"]["minimum_visible_verifier_targets"],
        },
        "issues": issues,
        "interpretation": [
            "The packet successfully escapes the singleton verifier-target failure mode.",
            "It is not yet clean enough for execution because the current evidence still exposes the gold test path and direct HFLocalAgent naming.",
            "The planner-list sibling is likely too weak to count as robust verifier competition without stronger rationale or replacement.",
        ],
        "recommended_next_stage": "stage10499_hf_local_multitest_packet_repair",
        "required_repairs": [
            "Redact or abstract direct gold test-path mentions from the evidence block before options are shown.",
            "Reduce symbol-name leakage by trimming or rewriting evidence snippets that directly announce HFLocalAgent as the behavior owner.",
            "Replace or strengthen the CLI planner-list sibling with a more semantically competitive hf_local-adjacent verifier target if possible.",
            "Run prompt-target leak audit again after the repair before any bounded execution materialization.",
        ],
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
