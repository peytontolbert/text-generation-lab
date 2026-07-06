# Stage8909 State-Dict Shape Migration Design

Passed: `True`

The local AgentKernel Lite artifact is a browser BitNet runtime export, not a verified PyTorch training checkpoint.

Direct loading is blocked because export key names, tokenizer vocab, learned positional embedding presence, and recovered control heads do not match the recovered PyTorch target directly.

Required before seed loading:

- source checkpoint or converter inventory
- explicit tokenizer/vocab migration decision
- export-to-PyTorch key mapping table
- per-key shape report
- head policy for retrieval, policy, intent, controller, scalar, and structured heads

Authority remains closed for model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion.
