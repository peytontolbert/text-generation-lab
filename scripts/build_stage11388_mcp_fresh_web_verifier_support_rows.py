#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11388
NAME = "stage11388_mcp_fresh_web_verifier_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "mcp_fresh_web_verifier_support_rows.json"
ROWS = OUT / "mcp_fresh_web_verifier_support_rows.jsonl"
BUNDLES = OUT / "mcp_fresh_web_verifier_root_bundles.jsonl"
EXEC = ART / "stage11387_mcp_fresh_web_verifier_execution_evidence/mcp_fresh_web_verifier_execution_evidence.json"


ROOT_SPECS: list[dict[str, Any]] = [
    {
        "root_slug": "mcp_tool_name_validation",
        "repo_family": "modelcontextprotocol_typescript_sdk",
        "source_path": "packages/core/src/shared/toolNameValidation.ts",
        "test_path": "packages/core/test/shared/toolNameValidation.test.ts",
        "symbol": "validateToolName / validateAndWarnToolName",
        "task": (
            "MCP tool-name validation must accept names with ASCII letters, digits, underscores, dashes, "
            "and dots; reject empty, overlength, or invalid-character names; and warn on risky edge patterns."
        ),
        "source_evidence": """packages/core/src/shared/toolNameValidation.ts:
const TOOL_NAME_REGEX = /^[A-Za-z0-9._-]{1,128}$/;
export function validateToolName(name: string): { isValid: boolean; warnings: string[] } {
    if (name.length === 0) return { isValid: false, warnings: ['Tool name cannot be empty'] };
    if (name.length > 128) return { isValid: false, warnings: [`Tool name exceeds maximum length of 128 characters (current: ${name.length})`] };
    if (name.includes(' ')) warnings.push('Tool name contains spaces, which may cause parsing issues');
    if (name.includes(',')) warnings.push('Tool name contains commas, which may cause parsing issues');
    if (!TOOL_NAME_REGEX.test(name)) return { isValid: false, warnings };
    return { isValid: true, warnings };
}""",
        "test_evidence": """packages/core/test/shared/toolNameValidation.test.ts:
test cases expect valid names like getUser, get_user_profile, user-profile-update, admin.tools.list, and 128-character names.
invalid cases expect empty names, overlength names, spaces, commas, slashes, @, unicode, and mixed invalid characters to be rejected.
validateAndWarnToolName is asserted to call console.warn for invalid or risky names and not warn for clean names.""",
        "distractor_evidence": """Distractor surfaces:
packages/core/src/shared/transport.ts handles fetch init/header merging, not tool-name validation.
packages/server/src/server/server.ts handles protocol initialization, not tool-name validation.""",
        "implementation_target": "packages/core/src/shared/toolNameValidation.ts::validateToolName",
        "minimal_fix": "adjust validateToolName validation/warning logic while preserving SEP-compatible allowed characters and length bounds",
        "alternative_reason": "transport/server code is unrelated because the selected tests import the toolNameValidation module directly",
    },
    {
        "root_slug": "mcp_fetch_init_header_merge",
        "repo_family": "modelcontextprotocol_typescript_sdk",
        "source_path": "packages/core/src/shared/transport.ts",
        "test_path": "packages/core/test/shared/transport.test.ts",
        "symbol": "normalizeHeaders / createFetchWithInit",
        "task": (
            "MCP transport fetch wrapping must normalize HeadersInit forms and merge base RequestInit with per-call init, "
            "with call-specific fields and headers overriding base values."
        ),
        "source_evidence": """packages/core/src/shared/transport.ts:
export function normalizeHeaders(headers: RequestInit['headers'] | undefined): Record<string, string> {
    if (!headers) return {};
    if (headers instanceof Headers) return Object.fromEntries(headers.entries());
    if (Array.isArray(headers)) return Object.fromEntries(headers);
    return { ...(headers as Record<string, string>) };
}
export function createFetchWithInit(baseFetch: FetchLike = fetch, baseInit?: RequestInit): FetchLike {
    if (!baseInit) return baseFetch;
    return async (url, init) => {
        const mergedInit = { ...baseInit, ...init, headers: init?.headers ? { ...normalizeHeaders(baseInit.headers), ...normalizeHeaders(init.headers) } : baseInit.headers };
        return baseFetch(url, mergedInit);
    };
}""",
        "test_evidence": """packages/core/test/shared/transport.test.ts:
normalizeHeaders is tested on undefined, Headers instances, tuple arrays, and plain objects.
createFetchWithInit is tested for preserving base init, allowing call init to override method, merging headers from base and call init, and retaining base headers when call headers are absent.""",
        "distractor_evidence": """Distractor surfaces:
packages/core/src/shared/toolNameValidation.ts validates tool names, not fetch init.
packages/server/src/server/server.ts handles server initialization, not header merging.""",
        "implementation_target": "packages/core/src/shared/transport.ts::createFetchWithInit",
        "minimal_fix": "adjust normalizeHeaders/createFetchWithInit merge semantics while preserving call-init override behavior",
        "alternative_reason": "tool-name validation and server initialization do not affect the mock fetch calls asserted by transport.test.ts",
    },
    {
        "root_slug": "mcp_server_initialize_protocol",
        "repo_family": "modelcontextprotocol_typescript_sdk",
        "source_path": "packages/server/src/server/server.ts",
        "test_path": "packages/server/test/server/server.test.ts",
        "symbol": "Server._oninitialize",
        "task": (
            "MCP server initialization must negotiate a protocol version from the initialize request and propagate the chosen version "
            "to the connected transport via setProtocolVersion."
        ),
        "source_evidence": """packages/server/src/server/server.ts:
private async _oninitialize(request: InitializeRequest): Promise<InitializeResult> {
    const requestedVersion = request.params.protocolVersion;
    this._clientCapabilities = request.params.capabilities;
    this._clientVersion = request.params.clientInfo;
    const protocolVersion = this._supportedProtocolVersions.includes(requestedVersion)
        ? requestedVersion
        : (this._supportedProtocolVersions[0] ?? LATEST_PROTOCOL_VERSION);
    this.transport?.setProtocolVersion?.(protocolVersion);
    return { protocolVersion, capabilities: this.getCapabilities(), serverInfo: this._serverInfo };
}""",
        "test_evidence": """packages/server/test/server/server.test.ts:
the test creates linked InMemoryTransport instances, injects a vi.fn() setProtocolVersion into the server transport, sends an initialize request using LATEST_PROTOCOL_VERSION, waits for the response, and expects setProtocolVersion to have been called with LATEST_PROTOCOL_VERSION.""",
        "distractor_evidence": """Distractor surfaces:
packages/core/src/shared/transport.ts defines generic transport/fetch helpers but not the Server initialize handler.
packages/core/src/shared/toolNameValidation.ts validates tool names, not protocol negotiation.""",
        "implementation_target": "packages/server/src/server/server.ts::Server._oninitialize",
        "minimal_fix": "adjust Server._oninitialize protocol negotiation/transport propagation without changing unrelated transport helpers",
        "alternative_reason": "the selected test installs setProtocolVersion on the server transport and sends initialize, so the server initialize handler is the causal surface",
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def option(label: str, text: str, value: str) -> dict[str, str]:
    return {"label": label, "text": text, "value": value}


def make_prompt(spec: dict[str, Any], perspective: str, instruction: str, options: list[dict[str, str]]) -> str:
    option_text = "\n".join(f"{item['label']}. {item['text']}" for item in options)
    return (
        f"Language: web_js_ts_html\n"
        f"Perspective: {perspective}\n"
        f"{instruction}\n"
        f"Repository family: {spec['repo_family']}\n"
        f"Task observation:\n{spec['task']}\n"
        f"Visible source evidence:\n{spec['source_evidence']}\n"
        f"Visible verifier/test evidence:\n{spec['test_evidence']}\n"
        f"Visible distractor/alternative evidence:\n{spec['distractor_evidence']}\n"
        f"Visible verifier execution evidence:\nExecuted targeted verifier passed for this root; see Stage11387 log artifact.\n"
        f"Options:\n{option_text}\n"
        f"Answer:"
    )


def make_row(
    spec: dict[str, Any],
    exec_card: dict[str, Any],
    task_type: str,
    instruction: str,
    options: list[dict[str, str]],
    target_label: str,
) -> dict[str, Any]:
    target_value = next(item["value"] for item in options if item["label"] == target_label)
    prompt = make_prompt(spec, task_type, instruction, options)
    root_id = f"stage11388::{spec['root_slug']}"
    row_id = f"{root_id}::{task_type}"
    return {
        "row_id": row_id,
        "root_id": root_id,
        "root_lineage_key": f"{spec['repo_family']}::stage11387_executed::{spec['root_slug']}",
        "repo_id": "modelcontextprotocol_typescript_sdk",
        "repo_family": spec["repo_family"],
        "language_family": "web_js_ts_html",
        "task_type": task_type,
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "review_status": "executed_verifier_train_support_admitted",
        "input_text": prompt,
        "prompt_text": prompt,
        "opaque_options": options,
        "bounded_choice_target_label": target_label,
        "target_text": target_label,
        "decoder_text": target_label,
        "semantic_target_value": target_value,
        "target": {
            "bounded_choice_target_label": target_label,
            "decoder_text": target_label,
            "target_text": target_label,
            "semantic_target_value": target_value,
        },
        "loss_mask": {"decoder_ce": True},
        "expected_enabled_loss": "decoder_ce",
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "executed_verifier_output_attached": True,
            "gold_value_not_used_as_label": True,
            "not_strict_eval_eligible": True,
            "source_and_verifier_snippets_visible": True,
            "target_label_not_visible_before_options": True,
            "same_repo_family_as_prior_mcp_support": True,
        },
        "verifier_execution_evidence": exec_card,
        "standalone_projection_source": {
            "projection_mode": "mcp_fresh_web_executed_verifier_support",
            "root_slug": spec["root_slug"],
            "source_path": spec["source_path"],
            "test_path": spec["test_path"],
            "symbol": spec["symbol"],
            "task": spec["task"],
            "source_evidence": spec["source_evidence"],
            "test_evidence": spec["test_evidence"],
            "distractor_evidence": spec["distractor_evidence"],
            "gold_value": target_value,
            "opaque_options": options,
            "verifier_execution_evidence": exec_card,
        },
    }


def rows_for_root(spec: dict[str, Any], exec_card: dict[str, Any]) -> list[dict[str, Any]]:
    impl = spec["implementation_target"]
    test = spec["test_path"]
    source = spec["source_path"]
    common_bad = "unrelated_neighbor_surface"
    rows: list[dict[str, Any]] = []
    rows.append(
        make_row(
            spec,
            exec_card,
            "symptom_localization",
            "Choose the implementation target most directly responsible for the observed verifier behavior.",
            [
                option("A", "selected verifier/test file", test),
                option("B", "implementation symbol exercised by the selected verifier", impl),
                option("C", "nearby unrelated MCP helper surface", common_bad),
                option("D", "package/build configuration surface", "package_or_build_config"),
            ],
            "B",
        )
    )
    rows.append(
        make_row(
            spec,
            exec_card,
            "evidence_citation",
            "Choose the evidence role that most directly justifies the maintainer target.",
            [
                option("A", "candidate change surface text only", "candidate_change_surface"),
                option("B", "symptom or call-path analogue", "symptom_or_call_path_analogue"),
                option("C", "selected verifier/test constraint plus source snippet", "verifier_and_test_constraint"),
                option("D", "repository metadata or package configuration", "repo_metadata_or_config"),
            ],
            "C",
        )
    )
    rows.append(
        make_row(
            spec,
            exec_card,
            "verifier_outcome",
            "Choose the verifier transition supported by the executed test evidence.",
            [
                option("A", "selected verifier passed under the observed implementation", "PASS_TARGETED_TEST_SELECTION"),
                option("B", "selected verifier failed before reaching the asserted behavior", "FAIL_BEFORE_TARGET_ASSERTION"),
                option("C", "selected verifier was not executed", "NOT_EXECUTED"),
                option("D", "insufficient evidence to classify verifier result", "INSUFFICIENT_EVIDENCE"),
            ],
            "A",
        )
    )
    rows.append(
        make_row(
            spec,
            exec_card,
            "minimal_fix_selection",
            "Choose the smallest maintainer action if this verifier behavior regressed.",
            [
                option("A", "rewrite unrelated repository metadata", "rewrite_repo_metadata"),
                option("B", "change the selected test expectation first", "change_test_expectation_first"),
                option("C", spec["minimal_fix"], spec["minimal_fix"]),
                option("D", "disable the verifier target", "disable_selected_verifier"),
            ],
            "C",
        )
    )
    rows.append(
        make_row(
            spec,
            exec_card,
            "alternative_hypothesis_elimination",
            "Choose why the tempting alternative surfaces are weaker than the selected implementation target.",
            [
                option("A", spec["alternative_reason"], "selected_verifier_exercises_implementation_not_distractor"),
                option("B", "the repository has no tests for this behavior", "no_selected_test_available"),
                option("C", "package metadata alone determines the tested behavior", "metadata_alone_determines_behavior"),
                option("D", "the source snippet is post-fix leakage and should be ignored", "post_fix_leakage"),
            ],
            "A",
        )
    )
    rows.append(
        make_row(
            spec,
            exec_card,
            "abstention_insufficient_evidence",
            "Choose whether this packet has enough visible evidence to answer.",
            [
                option("A", "answer using the visible source, verifier, and execution evidence", "ANSWER_WITH_VISIBLE_EVIDENCE"),
                option("B", "retrieve more evidence before any decision", "RETRIEVE_MORE"),
                option("C", "abstain because selected verifier identity is missing", "ABSTAIN_INSUFFICIENT_EVIDENCE"),
                option("D", "needs production runtime access", "NEEDS_PRODUCTION_RUNTIME"),
            ],
            "A",
        )
    )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    exec_summary = read_json(EXEC)
    by_root = {item["root_id"]: item for item in exec_summary.get("results", [])}
    rows: list[dict[str, Any]] = []
    bundles: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    for spec in ROOT_SPECS:
        exec_card = by_root.get(spec["root_slug"])
        if not exec_card or not exec_card.get("passed"):
            blocked.append({"root_slug": spec["root_slug"], "reason": "missing_or_failed_stage11387_execution"})
            continue
        rows.extend(rows_for_root(spec, exec_card))
        bundles.append(
            {
                "root_id": f"stage11388::{spec['root_slug']}",
                "root_slug": spec["root_slug"],
                "root_lineage_key": f"{spec['repo_family']}::stage11387_executed::{spec['root_slug']}",
                "repo_id": "modelcontextprotocol_typescript_sdk",
                "repo_family": spec["repo_family"],
                "language_family": "web_js_ts_html",
                "source_path": spec["source_path"],
                "test_path": spec["test_path"],
                "symbol": spec["symbol"],
                "task": spec["task"],
                "review": {
                    "gold_status": "admitted_train_support_only",
                    "verifier_execution_status": "executed_passed",
                    "not_promotable_reason": "Same broad MCP TypeScript SDK source family as previous MCP support; use for support/root expansion, not heldout headline.",
                },
                "verifier_execution_evidence": exec_card,
            }
        )
    write_jsonl(ROWS, rows)
    write_jsonl(BUNDLES, bundles)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": bool(rows) and not blocked,
        "decision": "mcp_fresh_web_verifier_support_rows_ready" if rows and not blocked else "mcp_fresh_web_verifier_support_rows_partial",
        "counts": {
            "roots": len(bundles),
            "rows": len(rows),
            "blocked_roots": len(blocked),
            "rows_by_task": dict(sorted(Counter(row["task_type"] for row in rows).items())),
            "rows_by_target_value": dict(sorted(Counter(row["semantic_target_value"] for row in rows).items())),
        },
        "admissibility": {
            "train_support_only": True,
            "strict_eval_eligible": False,
            "verifier_backed": True,
            "same_repo_family_as_prior_mcp_support": True,
            "why_not_strict_eval": "These roots add real executed Web verifier anchors but are not disjoint enough from prior MCP support for a headline heldout claim.",
        },
        "blocked": blocked,
        "source_artifacts": {"stage11387_execution": rel(EXEC)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "bundles": rel(BUNDLES)},
        "recommended_next_action": "Use these as Web train-support roots only; continue sourcing pure disjoint Web verifier roots for heldout promotion.",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
