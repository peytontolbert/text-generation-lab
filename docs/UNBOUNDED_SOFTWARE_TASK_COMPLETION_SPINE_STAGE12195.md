# Unbounded Software Task Completion Spine

Stage12195 adds the unbounded task-completion lane to the central research graph. This lane is blocked today, but the route is now explicit.

## Current Status

The current trainer can support:

- decoder CE on short serialized targets,
- denoise/suffix repair,
- structured auxiliary heads,
- bounded/listwise candidate scoring,
- retrieval and policy side heads,
- telemetry and anti-leak audits.

It cannot yet train full software-maintainer task completion as the primary unit because the repo lacks first-class trajectory training records and a closed-loop trajectory probe.

Current trainable full-episode supply:

- level_3+ episodes: `0`
- patch-trace episodes: `0`
- level_4 multi-step maintainer episodes: `0`

## Definition Of The New Training Unit

A valid unbounded task-completion training unit is not a bounded row or packable context row. It is:

```text
root + task
-> ordered typed events
-> causal state_before
-> candidate actions
-> chosen action
-> command/tool observation
-> patch trace or explicit no-patch reason
-> verifier result
-> state_after / state update
-> stop/continue decision
```

Rows that do not contain this tuple remain auxiliary.

## Admission Levels

- `level_0_context_only`: source/context/packable rows. Use for retrieval/context only.
- `level_1_verifier_only_no_patch`: command/verifier evidence with no patch. Use for verifier interpretation and stop-policy support only.
- `level_2_patch_context_no_execution`: patch/diff and verifier intent, but no command output. Use for patch-context mining, not closed-loop training.
- `level_3_single_step_closed_loop`: one ordered action, observation, verifier result, state update, and stop/continue decision.
- `level_4_multi_step_maintainer_episode`: two or more causal decision states with evidence updates, patch/verifier transitions, and terminal decision.

Training remains blocked until the level_3 diagnostic floor is met:

- at least 20 level_3+ episodes,
- at least 8 patch-trace episodes,
- at least 10 repositories,
- at least 3 languages,
- candidate-action floors met,
- no cross-source fabrication,
- leak and protected-overlap audits clean.

## Required Trainer Primitives

Add these only after data gates are met or in contract-only mode:

- `trajectory_data.py`: typed trajectory schema and batch builder.
- `closed_loop_trajectory_probe`: guarded trainer mode.
- typed action grammar: inspect/search/run/edit/patch/verify/abstain/stop.
- patch/diff targets with apply evidence and minimality metadata.
- verifier feedback targets: command, output, exit status, failure class, selected-test evidence.
- state update targets: facts added/removed, hypotheses invalidated, remaining blockers.
- stop policy targets grounded in verifier state and task completion.

## Source Routing

- `session_like_source_inventory_real`: best candidate for level_3/level_4 mining, but must be parsed same-source.
- `external_repo_commit_family_scale_v2`: level_2 patch-context candidate until verifier logs/state transitions are recovered.
- `merged_packable_examples`: auxiliary context/retrieval only.
- `stage12123`, `stage12144`, `stage12145`: level_1 verifier-only no-patch support only.
- `stage9756` harness packets: auxiliary until same-packet ordered repo trace exists.
- bounded transition rows and selected-test rows: auxiliary/projection only.

## Next Stage Sequence

1. `stage12193_same_source_patch_trace_episode_miner_request`
   Mine same-source patch-context and verifier/test evidence. Emit level_2 separately from level_3.

2. `same_source_session_trace_parser`
   Parse session-like raw traces into typed events, actions, observations, patches, verifier records, states, and stop decisions.

3. `same_root_verifier_rehydration`
   For level_2 patch-context rows, find or execute authorized same-root verifier commands. Do not infer verifier success from commit metadata.

4. `episode_quality_gate_v2`
   Re-run the Stage12191 ladder. Training remains blocked until the level_3 diagnostic floor passes.

5. `closed_loop_trajectory_probe_contract`
   Add trainer contract/preflight only. Do not run GPU training until episode gates and anti-cheat gates pass.

6. `closed_loop_trajectory_probe_tiny`
   Run a tiny diagnostic only after gate pass, on GPU 2 only, with protected compact and transition gates checked before/after.

## Non-Claims

This lane does not authorize:

- raw freeform codegen training,
- broad software maintainer replacement claims,
- executable patch repair claims,
- source-heldout Gemma claims,
- tokenizer replacement,
- training on bounded rows as if they were full episodes.

The graph should compound gains by routing every artifact to the right admission level, not by treating all rows as equivalent scale.
