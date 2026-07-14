#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11540
NAME = "stage11540_mcp_typescript_sdk_web_heldout_execution_artifact"
OUT = ART / NAME
SUMMARY = OUT / "mcp_typescript_sdk_web_heldout_execution_artifact.json"
PACKETS = OUT / "mcp_typescript_sdk_web_heldout_execution_packets.jsonl"
ROW_SHELLS = OUT / "mcp_typescript_sdk_web_heldout_row_shells.jsonl"

EXEC_DIR = ART / "stage11540_mcp_typescript_sdk_web_heldout_execution"
LOG_DIR = EXEC_DIR / "logs"
REPO = Path("/data/repositories/modelcontextprotocol__typescript-sdk")
GIT_HEAD = "22595b96855b34f00adcc6c1e7932ad68ea5139d"

PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "patch_impact",
    "minimal_fix_selection",
    "abstention_insufficient_evidence",
]

ROOT_SPECS = [
    {
        "slug": "server_protocol_registration",
        "package": "@modelcontextprotocol/server",
        "source": "packages/server/src/server/server.ts",
        "secondary": "packages/core/src/shared/protocol.ts",
        "test": "packages/server/test/server/server.test.ts",
        "log": "server_server_test.log",
        "status": "server_server_test.status",
        "task": "Server package verifier exercises MCP server registration and request handling behavior.",
    },
    {
        "slug": "server_streamable_http_transport",
        "package": "@modelcontextprotocol/server",
        "source": "packages/server/src/server/streamableHttp.ts",
        "secondary": "packages/core/src/shared/protocol.ts",
        "test": "packages/server/test/server/streamableHttp.test.ts",
        "log": "server_streamable_http_test.log",
        "status": "server_streamable_http_test.status",
        "task": "Server package verifier exercises streamable HTTP transport behavior and protocol integration.",
    },
    {
        "slug": "client_stdio_transport",
        "package": "@modelcontextprotocol/client",
        "source": "packages/client/src/stdio.ts",
        "secondary": "packages/core/src/shared/protocol.ts",
        "test": "packages/client/test/client/stdio.test.ts",
        "log": "client_stdio_test.log",
        "status": "client_stdio_test.status",
        "task": "Client package verifier exercises stdio transport behavior against protocol expectations.",
    },
    {
        "slug": "core_protocol_state_machine",
        "package": "@modelcontextprotocol/core",
        "source": "packages/core/src/shared/protocol.ts",
        "secondary": "packages/core/src/shared/transport.ts",
        "test": "packages/core/test/shared/protocol.test.ts",
        "log": "core_protocol_test.log",
        "status": "core_protocol_test.status",
        "task": "Core package verifier exercises protocol request/response and notification state handling.",
    },
    {
        "slug": "core_tool_name_validation",
        "package": "@modelcontextprotocol/core",
        "source": "packages/core/src/shared/toolNameValidation.ts",
        "secondary": "packages/core/src/types.ts",
        "test": "packages/core/test/shared/toolNameValidation.test.ts",
        "log": "core_tool_name_validation_test.log",
        "status": "core_tool_name_validation_test.status",
        "task": "Core package verifier exercises tool-name validation rules and rejected malformed names.",
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def snippet(path: Path, max_lines: int = 90) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path), "text": ""}
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[:max_lines])
    return {
        "exists": True,
        "line_start": 1,
        "line_end": len(text.splitlines()),
        "path": str(path),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "text": text,
    }


def status_code(spec: dict[str, str]) -> int | None:
    text = read(LOG_DIR / spec["status"]).strip()
    return int(text) if text.isdigit() else None


def packet(spec: dict[str, str]) -> dict[str, Any]:
    log_path = LOG_DIR / spec["log"]
    log = read(log_path)
    code = status_code(spec)
    passed = code == 0 and "passed" in log and "failed" not in log.lower()
    return {
        "root_id": f"stage11540::mcp_typescript_sdk::{spec['slug']}",
        "language_family": "web_js_ts_html",
        "repo_family": spec["package"],
        "git_repo_family": "modelcontextprotocol_typescript_sdk",
        "repo_path": str(REPO),
        "git_head": GIT_HEAD,
        "task_observation": spec["task"],
        "source_path": spec["source"],
        "secondary_source_path": spec["secondary"],
        "test_path": spec["test"],
        "visible_source_evidence": {
            "primary": snippet(REPO / spec["source"]),
            "secondary": snippet(REPO / spec["secondary"]),
        },
        "visible_verifier_evidence": {"test": snippet(REPO / spec["test"], max_lines=120)},
        "verifier_execution": {
            "dependency_hydration_command": "npx -p pnpm@10.26.1 pnpm install --frozen-lockfile --store-dir /data/tmp/pnpm-store-stage11540 --ignore-scripts",
            "focused_verifier_command": f"npx -p pnpm@10.26.1 pnpm --filter {spec['package']} test -- {spec['test'].replace('packages/' + spec['package'].split('/')[-1] + '/', '')}",
            "focused_verifier_exit_code": code,
            "observed_transition": "TARGETED_TEST_PASS" if passed else "TARGETED_TEST_FAILED_OR_BLOCKED",
            "raw_log_excerpt": log[-3000:],
            "log_artifact": rel(log_path),
        },
        "candidate_roles": [
            "candidate_change_surface",
            "verifier_and_test_constraint",
            "symptom_or_call_path_analogue",
            "dependency_or_test_environment_surface",
            "abstain_insufficient_evidence",
        ],
        "anti_cheat_precheck": {
            "executed_verifier_output_attached": True,
            "target_label_not_assigned_yet": True,
            "root_split_pending": True,
            "not_existing_openhands_or_llama_heldout": True,
            "do_not_train_until_gold_and_split": True,
        },
        "admission_status": "executed_verifier_materialized_pending_gold_and_split",
        "trainable_now": False,
        "strict_eval_eligible_now": False,
    }


def row_shells(root_packet: dict[str, Any]) -> list[dict[str, Any]]:
    option_lines = "\n".join(f"option {idx + 1}: {role}" for idx, role in enumerate(root_packet["candidate_roles"]))
    common = (
        f"Repository family: {root_packet['git_repo_family']}\n"
        f"Task observation: {root_packet['task_observation']}\n"
        f"Primary source: {root_packet['source_path']}\n"
        f"Selected verifier: {root_packet['test_path']}\n"
        f"Verifier transition: {root_packet['verifier_execution']['observed_transition']}\n"
        f"Verifier log excerpt:\n{root_packet['verifier_execution']['raw_log_excerpt']}\n"
        f"Options:\n{option_lines}\n"
    )
    return [
        {
            "row_id": f"{root_packet['root_id']}::{perspective}",
            "root_id": root_packet["root_id"],
            "language_family": root_packet["language_family"],
            "task_type": perspective,
            "input_text": f"Perspective: {perspective}\nUse only visible source and verifier evidence.\n{common}",
            "opaque_options": [],
            "semantic_candidate_roles": root_packet["candidate_roles"],
            "bounded_choice_target_label": None,
            "semantic_target_value": None,
            "target_status": "pending_gold_adjudication",
            "strict_eval_eligible": False,
            "train_support_only": False,
            "anti_cheat": {
                "executed_verifier_output_attached": True,
                "target_not_assigned": True,
                "target_label_not_visible_before_options": True,
                "do_not_score_or_train": True,
            },
        }
        for perspective in PERSPECTIVES
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    packets = [packet(spec) for spec in ROOT_SPECS]
    rows = [row for pkt in packets for row in row_shells(pkt)]
    passed_packets = [pkt for pkt in packets if pkt["verifier_execution"]["focused_verifier_exit_code"] == 0]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": len(passed_packets) == len(packets),
        "decision": "mcp_typescript_sdk_web_execution_materialized_pending_gold_and_split",
        "counts": {
            "executed_root_packets": len(packets),
            "passed_root_packets": len(passed_packets),
            "row_shells": len(rows),
            "train_ready_rows": 0,
            "strict_eval_ready_rows": 0,
        },
        "claim_boundary": [
            "This is execution evidence and row-shell materialization only.",
            "Rows are not trainable or scoreable until gold adjudication, anti-cheat review, and split assignment are complete.",
            "The package is useful for Web heldout/root supply, not a model-score improvement by itself.",
        ],
        "outputs": {
            "summary": rel(SUMMARY),
            "packets": rel(PACKETS),
            "row_shells": rel(ROW_SHELLS),
            "raw_execution_dir": rel(EXEC_DIR),
        },
        "next_actions": [
            "Assign sealed heldout or train-support split by root before target labels are filled.",
            "Fill six-perspective gold answers with deterministic opaque options.",
            "Run prompt-target leak and root-overlap audits before any scoring package includes these rows.",
        ],
    }
    write_jsonl(PACKETS, packets)
    write_jsonl(ROW_SHELLS, rows)
    write_json(SUMMARY, summary)
    write_json(SUMMARIES / f"{NAME}.json", summary)


if __name__ == "__main__":
    main()
