#!/usr/bin/env python3
"""Build Stage12261 episode graph candidate schema/validator contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12261_episode_graph_candidate_schema_contract"


def load_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.exists():
        return {"_missing": rel}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> int:
    stage12260 = load_json("runs/summaries/stage12260_codex_chat_task_boundary_miner.json")
    contract: dict[str, Any] = {
        "stage": STAGE,
        "artifact_type": "episode_graph_candidate_schema_contract",
        "decision": "episode_graph_schema_ready_projection_still_blocked_until_validator_exists",
        "training_allowed": False,
        "claim_boundary": (
            "Schema/control artifact only. Defines source-agnostic episode graph candidates and validation levels. "
            "It emits no candidates, admits no roots, and authorizes no training."
        ),
        "source_adapter_boundary": {
            "principle": "Codex chats are a source adapter, not the dataset format.",
            "codex_inputs": [
                "stage12258 per-chat source manifests",
                "stage12259 paired tool call/observation refs",
                "stage12260 task windows",
            ],
            "generic_output": "episode_graph_candidate",
            "forbidden": [
                "raw Codex/Cursor rows as training rows",
                "source-specific fields required by trainer",
                "raw message text/tool output/arguments/patch body in candidate graph",
            ],
        },
        "stage12260_input_status": {
            "task_windows": (stage12260.get("counts") or {}).get("task_windows"),
            "candidate_windows_with_command_observation": (stage12260.get("counts") or {}).get("candidate_windows_with_command_observation"),
            "patch_and_verifier_ref_windows": (stage12260.get("counts") or {}).get("patch_and_verifier_ref_windows"),
        },
        "required_schema": {
            "top_level": [
                "schema_version",
                "candidate_id",
                "source_adapter",
                "source_refs",
                "root",
                "task",
                "ordered_events",
                "states",
                "decision_steps",
                "observations",
                "patch_trace",
                "verifier_results",
                "stop_continue",
                "admission",
                "privacy_security",
                "dedupe_lineage",
                "audit_trail",
            ],
            "source_refs": [
                "snapshot_id",
                "physical_source_ids",
                "chat_or_session_ids",
                "event_span_refs",
                "tool_pair_refs",
                "raw_payload_digests",
                "adapter_payload_refs",
            ],
            "root": [
                "root_id_candidate",
                "repo_family",
                "cwd_boundary_ref",
                "language_family_candidate",
                "license_security_flags",
                "split_intent",
            ],
            "decision_step": [
                "step_id",
                "state_before_ref",
                "candidate_actions",
                "chosen_action",
                "action_grammar_type",
                "observation_refs",
                "state_update_ref",
                "rationale_evidence_refs",
            ],
            "canonical_action_grammar": [
                "inspect",
                "search",
                "run",
                "edit",
                "patch",
                "verify",
                "abstain",
                "stop",
                "delegate",
                "handoff",
            ],
        },
        "validation_levels": [
            {
                "level": "V0_source_envelope",
                "requires": ["source lineage", "snapshot id", "root/cwd boundary", "event span refs", "no raw leakage"],
            },
            {
                "level": "V1_ordering_pairing",
                "requires": ["monotonic ordered events", "paired tool call/observation where used", "no unpaired execution as evidence"],
            },
            {
                "level": "V2_task_boundary",
                "requires": ["coherent root and task window", "no cross-chat/root stitching unless explicit handoff evidence exists"],
            },
            {
                "level": "V3_causal_tuple",
                "requires": ["state_before", "candidate_actions", "chosen_action", "observation", "state_update", "stop_continue"],
            },
            {
                "level": "V4_patch_verifier",
                "requires": ["same-source patch/edit/no-patch evidence", "verifier command/output", "causal order patch/action before verifier"],
            },
            {
                "level": "V5_admission_qc",
                "requires": ["dedupe", "repo caps", "language floors", "leak/protected-overlap clean", "ENV/dependency noise rejected"],
            },
        ],
        "admission_mapping": {
            "level_0_context_only": "context/source only; retrieval support only",
            "level_1_verifier_only_no_patch": "verifier/command evidence but no patch trace",
            "level_2_patch_context_no_execution": "patch/diff plus verifier intent but no observed command output",
            "level_3_single_step_closed_loop": "one causal decision state with action, observation, verifier result, state update, stop/continue",
            "level_4_multi_step_maintainer_episode": "two or more causal decision states with terminal decision",
        },
        "fail_closed_rules": [
            "missing source lineage, root, task boundary, event order, or source snapshot",
            "nonmonotonic event order or ambiguous task span",
            "raw Codex/Cursor rows directly emitted as train rows",
            "cross-source patch-command-verifier stitching without explicit handoff evidence",
            "unpaired tool call/output used as observation evidence",
            "patch success inferred from commit metadata, assistant prose, or file mention",
            "verifier success inferred from PASS_CURRENT_BUILD, broad build status, or unrelated later command",
            "ENV_BLOCKED/dependency/install noise counted as task success",
            "missing state_before/candidate_actions/chosen_action/observation/state_update/stop_continue for level_3+",
            "secrets, protected overlap, train/eval leakage, or raw payload leakage",
            "GPT reviewer disagreement with deterministic gates treated as reject/quarantine; GPT cannot override",
        ],
        "projection_policy_after_admission": {
            "level_0": ["retrieval/context selection"],
            "level_1": ["verifier interpretation", "failure classification", "insufficient-evidence abstain", "limited stop policy"],
            "level_2": ["patch judgment", "changed-file prediction", "minimality/localization", "verifier intent"],
            "level_3_plus": ["next action", "action ranking", "state update", "verifier feedback", "stop/continue", "counterfactual negatives"],
            "level_4": ["multi-step planning", "long-horizon state tracking", "recovery-after-failure", "terminal completion policy"],
        },
        "next_stage": {
            "stage": "stage12262_episode_graph_candidate_validator_skeleton",
            "purpose": "Implement schema validation and fail-closed admission-level checks before projecting root candidates.",
            "training_allowed": False,
        },
    }
    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", contract)
    write_json(out_dir / "episode_graph_candidate_schema_contract.json", contract)
    md = f"""# Stage12261 Episode Graph Candidate Schema Contract

## Decision

`{contract["decision"]}`

No training is allowed.

## Core Rule

Codex chats are source-adapter inputs. The dataset unit is a source-agnostic `episode_graph_candidate`:

`root + task -> ordered_events -> states -> decision_steps -> observations -> patch_trace/no_patch_reason -> verifier_results -> stop_continue -> admission`

Projection rows can only be derived after deterministic admission.
"""
    write_text(out_dir / "EPISODE_GRAPH_CANDIDATE_SCHEMA_CONTRACT_STAGE12261.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "EPISODE_GRAPH_CANDIDATE_SCHEMA_CONTRACT_STAGE12261.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
