# Stage8908 Tokenizer Special Token Compatibility Audit

Passed: `True`

The local AgentKernel Lite tokenizer is `agentkernel_bytelevel_bpe_v1` with core IDs `<pad>=0`, `<s>=1`, `</s>=2`, `<unk>=3`.

Recovered AgentKernel special tokens are contiguous from 8192 through 8206:

<AK_USER>, <AK_CHAT>, <AK_THINK>, <AK_DEEP_RESEARCH>, <AK_CONTEXT>, <AK_EVIDENCE>, <AK_CANDIDATE>, <AK_QUERY_REWRITE>, <AK_RERANK>, <AK_GATHER_CONTEXT>, <AK_RESPOND>, <AK_SUFFICIENT>, <AK_INSUFFICIENT>, <AK_ANSWER>, <AK_JSON>

The full tokenizer is not swappable into the recovered target as-is because the local export vocab is 8207 while the recovered target config still uses 1506. This requires an explicit tokenizer migration and embedding/lm-head resize or a matching checkpoint/config source.

V2 software-maintainer tokens remain a planned migration, not an ad hoc edit:

<AK_OBSERVE>, <AK_ORIENT>, <AK_ACT>, <AK_VERIFY>, <AK_REPAIR>, <AK_RETRIEVE>, <AK_PATCH>, <AK_TEST>, <AK_ABORT>, <AK_HOLD_LONG_OUTPUT>, <AK_BOUND_DECODER>, <AK_VTR>

Authority remains closed for model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion.
