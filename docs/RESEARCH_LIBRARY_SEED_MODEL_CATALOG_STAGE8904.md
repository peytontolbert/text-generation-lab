# Stage8904 Research Library Seed Model Catalog

Passed: `True`

This stage catalogs useful models from the Hugging Face research-library collection and local `/data/repository_library` exports without downloading, loading, or executing any model.

Decision: the only direct core-seed candidate is the local AgentKernel Lite 100M-ish encoder-decoder export, pending tokenizer/architecture compatibility audit. The other models are useful as frozen teachers, retrievers, rerankers, verifier priors, planner proposal sources, or representation-distillation sidecars.

Most useful side candidates: repo-state-grounding, jepa-repo-state, cross-encoder-reranker, candidate-row-reranker, verifier-accept-policy, span-infill-gate, bug-localization, cross-modal-retrieval, paper-to-code, repo-conditioned-adapter, query-rewriter, world-planner-adapter, M1 paper embeddings.

This opens no model execution, downloads, training, decoder CE, denoise CE, runtime, `/arxiv` walk, data mining, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion.
