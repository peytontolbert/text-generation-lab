# Stage8655 Source-Backed Graph/Symbol-Binding Recovery Plan

This is the no-authority build plan for restoring the two remaining hard blockers: `repo_state_graph_v1_enrichment` and `symbol_binding`.

## Source Sets
- `repo_graph_sources`
  - `/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl` exists=True
  - `/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl` exists=True
  - `/arxiv/TOLBERT_BRAIN/scripts/codegraph_core.py` exists=True
  - `/arxiv/TOLBERT_BRAIN/scripts/code_graph.py` exists=True
  - `/arxiv/TOLBERT_BRAIN/scripts/repo_graph.py` exists=True
  - `/arxiv/TOLBERT_BRAIN/modules/program_graph.py` exists=True
- `retrieval_sources`
  - `/arxiv/TOLBERT_BRAIN/scripts/retrieval_sandbox.py` exists=True
  - `/arxiv/TOLBERT_BRAIN/scripts/eval_retrieval.py` exists=True
  - `/arxiv/datasets/google--code_x_glue_tc_nl_code_search_adv` exists=True
  - `/arxiv/repositories/camel-ai__camel/camel/retrievers/bm25_retriever.py` exists=True
  - `/arxiv/repositories/FlagEmbedding/FlagEmbedding/inference/auto_reranker.py` exists=True
- `agent_trace_sources`
  - `/arxiv/datasets/nvidia--Open-SWE-Traces` exists=True
  - `/arxiv/repositories/SWE-agent__SWE-agent` exists=True
  - `/arxiv/repositories/Aider-AI__aider` exists=True
  - `/arxiv/repositories/OpenAutoCoder__Agentless` exists=True
- `judge_sources`
  - `scripts/objective_row_judge.py` exists=True
  - `scripts/shortcut_baseline_audit.py` exists=True
  - `configs/software_maintainer/action_feature_registry.json` exists=True
  - `configs/software_maintainer/support_systems_recovery_index_stage8653.json` exists=True

## Gate Cards
- `source_inventory_card`: Declare exact source roots, file counts, schema samples, and allowed roles before extracting rows.
- `shared_feature_extraction_card`: Normalize feature names before mining so Stage8058-style feature drift cannot recur.
- `bm25_dense_retrieval_baseline_card`: Measure lexical and dense evidence before training symbol binding or graph rows.
- `graph_shortcut_card`: Block graph rows if degree/query/node IDs solve labels.
- `symbol_binding_counterfactual_card`: Guarantee real transition learning instead of positive-only memorization.
- `junk_risk_ood_ranker_card`: Route bad/ambiguous rows before loss.
- `split_dedup_cluster_card`: Prevent leakage and redundant islands before scale.
- `loss_authority_card`: Keep this as structured-only until gates pass.

## Build Order
- `8655a` `source_inventory`: sample/read source schemas only; emit inventory; no model/runtime
- `8655b` `shared_feature_extractor`: write common feature normalizer for graph/symbol rows; audit alias parity
- `8655c` `retrieval_baseline`: build BM25/dense/hybrid retrieval cards over candidate evidence; no training
- `8655d` `graph_enrichment_manifest`: emit opaque repo_state_graph_v1 rows with graph shortcut card
- `8655e` `symbol_binding_manifest`: emit balanced symbol binding rows with counterfactual obligations
- `8655f` `junk_ranker_gate`: train-free deterministic/logistic-ready ranker card; route bad rows before loss
- `8655g` `aggregate_readiness`: aggregate all cards; only then propose a tiny structured-head training candidate

## Authority Boundary
- Model execution: closed
- Decoder CE: closed
- Denoise CE: closed
- Runtime/source/body/Gemma/harness/scoring/promotion: closed
