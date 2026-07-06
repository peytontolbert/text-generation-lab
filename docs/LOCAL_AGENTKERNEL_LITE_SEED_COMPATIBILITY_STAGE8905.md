# Stage8905 Local AgentKernel Lite Seed Compatibility Audit

Passed: `True`

This is a no-execution compatibility audit over the local AgentKernel Lite browser BitNet export.

Finding: the export matches the recovered target on major dimensions (`d_model=640`, `d_ff=2048`, 6 layers, 10 heads, 4096 positions, RoPE theta 1e6), but it is not directly trainable in the recovered PyTorch trainer as-is.

Primary blockers:

- tokenizer/vocab mismatch: local export vocab is 8207 while the recovered target default is 1506
- retrieval and agent policy heads are absent in the export metadata but expected in the current recovered control surface
- the artifact is a browser BitNet runtime export, not a verified PyTorch training checkpoint
- no state-dict key/shape mapping has been audited

Allowed use now: lineage/reference only. Do not load, train, resize, convert, or execute it until the next audits are built and passed.

Authority remains closed for model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion.
