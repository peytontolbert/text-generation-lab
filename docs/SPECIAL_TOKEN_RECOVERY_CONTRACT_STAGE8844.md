# Stage8844 Special Token Recovery Contract

## Status

Stage8844 recovers the special-token contract for the 100M software maintainer path from preserved tokenizer artifacts under `/arxiv`.

This is a recovery/control artifact only. It opens no training, decoder CE, runtime, source/body emission, Gemma, harness, scoring, or promotion authority.

Recovered machine-readable contract:

- `configs/tokenizer/agentkernel_special_token_contract_stage8844.json`
- `runs/summaries/stage8844_special_token_recovery_contract.json`

## Recovered Tokenizer

Full 100M training must use the recovered AgentKernel tokenizer:

- tokenizer kind: `agentkernel_bytelevel_bpe_v1`
- vocabulary size: `1506`
- pad token/id: `<pad>` / `0`
- BOS token/id: `<s>` / `1`
- EOS token/id: `</s>` / `2`
- UNK token/id: `<unk>` / `3`
- added special tokens: `150`
- AgentKernel structural tokens: `146`
- copy-source slot tokens: `24`

Preserved source artifacts:

- tokenizer JSON: `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/tokenizer/tokenizer.json`
- tokenizer config: `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/tokenizer/tokenizer_config.json`

Hashes:

- tokenizer JSON: `c268a145d01e26047d7773d9888c13902ab0cbf0e59da333ba2b686fec4ae324`
- tokenizer config: `0987f58448a3163615eb167d93973fa209d7ccb12dd5c7a35c1e8ab166299be0`

The byte fallback tokenizer remains valid only for tiny recovery probes with explicit audit. It must not silently replace the 1506-vocab tokenizer for full 100M training.

## AgentKernel Token Groups

The recovered tokenizer reserves structural AgentKernel tokens for dialogue state, evidence routing, retrieval, memory, verification, action spaces, software-maintenance actions, rendering, and copy-source slots.

Important groups recovered into the contract:

- core dialogue/state: `<AK_USER>`, `<AK_CHAT>`, `<AK_THINK>`, `<AK_PLAN>`, `<AK_STATE>`, `<AK_CONTEXT>`, `<AK_ACTIVE_CONTEXT>`
- evidence/retrieval: `<AK_EVIDENCE>`, `<AK_EVIDENCE_ID>`, `<AK_RETRIEVE>`, `<AK_RETRIEVE_AGAIN>`, `<AK_RET_EXACT>`, `<AK_RET_SEMANTIC>`, `<AK_RET_HYBRID>`
- sufficiency/OOD: `<AK_SUFFICIENT>`, `<AK_INSUFFICIENT>`, `<AK_UNCERTAIN>`, `<AK_INSUFFICIENT_EVIDENCE>`, `<AK_NEEDS_VERIFICATION>`, `<AK_OOD>`
- answer/rendering: `<AK_ANSWER>`, `<AK_RENDER>`, `<AK_JSON>`, `<AK_CONTENT>`, `</AK_CONTENT>`, `<AK_END>`
- verification: `<AK_VERIFY>`, `<AK_REFLECT>`, `<AK_CHECK_FACT>`, `<AK_CHECK_CONSISTENCY>`, `<AK_CHECK_EVIDENCE>`
- action spaces: `<AK_ACTION_SPACE_CODE>`, `<AK_ACTION_SPACE_ARTIFACT>`, `<AK_ACTION_SPACE_RETRIEVAL>`, `<AK_ACTION_SPACE_RESPOND>`, `<AK_STRUCTURED>`
- software maintenance: `<AK_RET_CODE>`, `<AK_ARTIFACT_REPAIR>`, `<AK_SOURCE_INSPECT>`, `<AK_PATCH_BUILD>`, `<AK_SAFE_STOP>`, `<AK_SOURCE_SLOTS>`
- copy slots: `<AK_COPY_USER_SOURCE_1>` through `<AK_COPY_USER_SOURCE_24>`

These tokens are not ordinary prose. They are structural/control vocabulary. They may appear in authorized structured/control surfaces, but they must not be accidentally copied into user-facing final decoder output.

## Legacy Internal-Control Families

Session and repo recovery also preserved older internal/control token families. These are not part of the 1506 AgentKernel `<AK_...>` inventory, but they are still important because historical rows and failure probes used them.

Rows containing these families in decoder text must not go to normal bounded decoder CE:

- `<MTC...>`
- `<MT...>`
- `<COPY...>`
- `COPY:`
- `<SEM...>`
- `<CTRL...>`
- `<PLAN...>`
- `<MNSB...>`
- `<PYPLAN...>`
- `POLICY_*`
- `CONTROL_*`
- `INTERNAL_*`
- `decoder_control`

Correct route:

- use as denoise/repair examples when the task is internal-token cleanup
- use as negatives when teaching suppression/abstain behavior
- quarantine or review when they appear in ordinary positive targets
- block from `KEEP_BOUNDED_DECODER` unless an explicit specialized objective authorizes them

## Training Rules

Before any bounded decoder CE or generation probe:

1. Tokenizer kind and hashes must match the recovered 1506-vocab tokenizer.
2. Model `vocab_size` must be `1506`.
3. PAD/BOS/EOS/UNK IDs must match `0/1/2/3`.
4. Decoder targets must be within the audited target-length cap.
5. User-facing decoder targets must have zero legacy internal/control-token hits.
6. Structural `<AK_...>` tokens must be authorized by the row route and target surface.
7. Loss masks must explicitly enable decoder CE for the row.
8. Token-level telemetry must include leak checks, EOS/length checks, short/junk checks, and repetition checks.

Critical recovered lesson: zero internal-token leak is not enough. Stage8392-style suppression can produce empty or junk outputs. Every future decoder probe must require both leak-free and contentful, non-repetitive output.

## Implementation Gaps

Recovered but still needing hardening:

- unify internal-token regex across `structured_dataset_junk_ranker.py`, `dataset_junk_ood_ranker_v1.py`, and `training_loop.py`
- generate tokenizer-ID suppression masks from the recovered tokenizer, not only string regexes
- make tokenizer hash compatibility a hard trainer preflight
- audit `<AK_...>` structural-token appearance by route, not just by regex
- add `internal_token_logit_summary` to future model-output packet telemetry before any real model-output capture

## Next

Next best step:

`stage8845_special_token_guard_unification_design`

It should design one shared token guard used by dataset judge, loss-mask compiler, trainer preflight, model-output packet telemetry, and denoise routing.
