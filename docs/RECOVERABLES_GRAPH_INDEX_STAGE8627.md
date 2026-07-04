# Stage8627 Recoverables Graph Index

This stage attaches the Stage8625 `/arxiv` recoverable-candidate scrape to the central research graph. It keeps the graph compact by adding aggregate category/root/keyword nodes and explicit high-value recovery-source nodes.

No files were copied from candidates, no checkpoints were loaded, no model execution occurred, and no training authority was opened.

## Counts

```json
{
  "candidate_rows": 13833,
  "category_counts": {
    "architecture_related": 669,
    "dataset_source": 13139,
    "keyword_related": 6,
    "likely_direct_recovery": 19
  },
  "high_value_count": 3083,
  "keyword_counts": {
    "100m": 55,
    "agentkernel": 25,
    "agentkernel_lite": 4,
    "codegraph": 6,
    "model_stack": 4,
    "program_graph": 5,
    "repo_graph": 5,
    "seq2seq": 63
  }
}
```

## Top Roots

- `/arxiv/repositories/NousResearch__hermes-agent`: 2836
- `/arxiv/repositories/diffusers`: 2407
- `/arxiv/repositories/agent-framework`: 2118
- `/arxiv/repositories/DeepSpeed`: 1309
- `/arxiv/repositories/OpenHands__software-agent-sdk`: 1134
- `/arxiv/repositories/Model-Optimizer`: 961
- `/arxiv/repositories/OpenHands__OpenHands`: 913
- `/arxiv/repositories/LlamaFactory`: 508
- `/arxiv/repositories/Aider-AI__aider`: 344
- `/arxiv/repositories/SWE-agent__SWE-agent`: 251
- `/arxiv/repositories/CodeXGLUE`: 212
- `/arxiv/repositories/SWE-agent__mini-swe-agent`: 191
- `/arxiv/repositories/Agent-Framework-Samples`: 178
- `/arxiv/datasets`: 153
- `/arxiv/repositories/SWE-agent__SWE-ReX`: 81
- `/arxiv/TOLBERT_BRAIN`: 66
- `/arxiv/repositories/RepairThemAll`: 52
- `/arxiv/repositories/TOLBERT`: 47
- `/arxiv/preserved_checkpoints_20260609`: 25
- `/arxiv/repositories/denoising-diffusion-pytorch`: 21

## Prioritized High-Value Sources

- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1074_direct_answer_decoder_v415/agentkernel_lite_encdec_manifest.json` hits=['agentkernel', 'seq2seq', '100m', 'model_stack', 'agentkernel_lite']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/agentkernel_lite_encdec_manifest.json` hits=['agentkernel', 'seq2seq', '100m', 'model_stack', 'agentkernel_lite']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage972_stage968_kbpp_smoke_v415/agentkernel_lite_encdec_manifest.json` hits=['agentkernel', 'seq2seq', '100m', 'model_stack', 'agentkernel_lite']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415/agentkernel_lite_encdec_manifest.json` hits=['agentkernel', 'seq2seq', '100m', 'model_stack', 'agentkernel_lite']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1074_direct_answer_decoder_v415/checkpoints/latest.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1074_direct_answer_decoder_v415/model/config.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1074_direct_answer_decoder_v415/tokenizer/tokenizer.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1074_direct_answer_decoder_v415/tokenizer/tokenizer_config.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/checkpoints/latest.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/model/config.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/tokenizer/tokenizer.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/tokenizer/tokenizer_config.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage972_stage968_kbpp_smoke_v415/checkpoints/latest.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage972_stage968_kbpp_smoke_v415/model/config.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage972_stage968_kbpp_smoke_v415/tokenizer/tokenizer.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage972_stage968_kbpp_smoke_v415/tokenizer/tokenizer_config.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415/model/config.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415/tokenizer/tokenizer.json` hits=['agentkernel', 'seq2seq', '100m']
- `likely_direct_recovery` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415/tokenizer/tokenizer_config.json` hits=['agentkernel', 'seq2seq', '100m']
- `architecture_related` `/arxiv/TOLBERT_BRAIN/scripts/repo_graph.py` hits=['codegraph', 'repo_graph', 'program_graph']
- `architecture_related` `/arxiv/repositories/TOLBERT/scripts/repo_graph.py` hits=['codegraph', 'repo_graph', 'program_graph']
- `architecture_related` `/arxiv/TOLBERT_BRAIN/tolbert_brain/data_builder.py` hits=['repo_graph', 'program_graph']
- `architecture_related` `/arxiv/TOLBERT_BRAIN/modules/program_graph.py` hits=['program_graph']
- `architecture_related` `/arxiv/TOLBERT_BRAIN/scripts/build_repo_tree_of_life.py` hits=['repo_graph']
- `architecture_related` `/arxiv/TOLBERT_BRAIN/scripts/code_graph.py` hits=['codegraph']
- `architecture_related` `/arxiv/TOLBERT_BRAIN/scripts/codegraph_core.py` hits=['codegraph']
- `architecture_related` `/arxiv/repositories/CodeXGLUE/Code-Code/code-refinement/code/run.py` hits=['seq2seq']
- `architecture_related` `/arxiv/repositories/CodeXGLUE/Code-Code/code-to-code-trans/code/run.py` hits=['seq2seq']
- `architecture_related` `/arxiv/repositories/CodeXGLUE/Code-Text/code-to-text/code/run.py` hits=['seq2seq']
- `architecture_related` `/arxiv/repositories/CodeXGLUE/Text-Text/text-to-text/code/run.py` hits=['seq2seq']
- `architecture_related` `/arxiv/repositories/Model-Optimizer/examples/windows/onnx_ptq/whisper/whisper_onnx_quantization.py` hits=['seq2seq']
- `architecture_related` `/arxiv/repositories/NousResearch__hermes-agent/optional-skills/mlops/huggingface-tokenizers/SKILL.md` hits=['100m']
- `architecture_related` `/arxiv/repositories/NousResearch__hermes-agent/skills/creative/touchdesigner-mcp/references/pitfalls.md` hits=['100m']
- `architecture_related` `/arxiv/repositories/NousResearch__hermes-agent/website/docs/user-guide/skills/optional/mlops/mlops-huggingface-tokenizers.md` hits=['100m']
- `architecture_related` `/arxiv/repositories/TOLBERT/modules/program_graph.py` hits=['program_graph']
- `architecture_related` `/arxiv/repositories/TOLBERT/scripts/build_repo_tree_of_life.py` hits=['repo_graph']
- `architecture_related` `/arxiv/repositories/TOLBERT/scripts/code_graph.py` hits=['codegraph']
- `architecture_related` `/arxiv/repositories/TOLBERT/scripts/codegraph_core.py` hits=['codegraph']
- `architecture_related` `/arxiv/TOLBERT_BRAIN/scripts/build_joint_training_bundle_v2.py` hits=[]
- `architecture_related` `/arxiv/TOLBERT_BRAIN/scripts/build_repositories_spans.py` hits=[]
- `architecture_related` `/arxiv/repositories/Aider-AI__aider/aider/help.py` hits=[]
- `architecture_related` `/arxiv/repositories/Aider-AI__aider/aider/repomap.py` hits=[]
- `architecture_related` `/arxiv/repositories/Aider-AI__aider/aider/website/_posts/2023-12-21-unified-diffs.md` hits=[]
- `architecture_related` `/arxiv/repositories/Aider-AI__aider/aider/website/_posts/2024-05-22-linting.md` hits=[]
- `architecture_related` `/arxiv/repositories/Aider-AI__aider/aider/website/docs/unified-diffs.md` hits=[]
- `architecture_related` `/arxiv/repositories/Aider-AI__aider/benchmark/refactor_tools.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/Development.md` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/enterprise/enterprise_local/README.md` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/enterprise/integrations/github/data_collector.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/enterprise/integrations/github/queries.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/enterprise/server/app_lifespan/saas_app_lifespan_service.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/enterprise/tests/unit/test_saas_lifespan.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/kind/cluster.yaml` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/kind/manifests/nginx.yaml` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/app_server/app.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/app_server/app_lifespan/app_lifespan_service.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/app_server/app_lifespan/oss_app_lifespan_service.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/app_server/config.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/app_server/integrations/github/queries.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/app_server/integrations/github/service/branches_prs.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/app_server/integrations/github/service/features.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/app_server/integrations/github/service/resolver.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/app_server/integrations/gitlab/service/features.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/openhands/server/app.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/skills/agent-builder.md` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/skills/kubernetes.md` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/tests/unit/integrations/github/test_github_branches.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__OpenHands/tests/unit/integrations/github/test_suggested_tasks.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/.agents/skills/manage-evals/references/eval-infrastructure.md` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/.github/scripts/check_deprecations.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/.github/scripts/check_sdk_api_breakage.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/.github/workflows/review-thread-gate.yml` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/AGENTS.md` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/openhands-sdk/openhands/sdk/conversation/base.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/openhands-sdk/openhands/sdk/security/defense_in_depth/pattern.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/openhands-tools/openhands/tools/terminal/utils/command.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/tests/sdk/context/view/test_view_manipulation_indices.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/tests/sdk/critic/test_critic_display.py` hits=[]
- `architecture_related` `/arxiv/repositories/OpenHands__software-agent-sdk/tests/sdk/skills/test_skill_commands.py` hits=[]

## Next Recovery Use

Use this index to select exact source material for rebuilding missing objective builders. Priority should be direct AgentKernel artifacts first, then repo graph/codegraph assets, then agent repos and software datasets.

## Metrics

```json
{
  "attached_graph_edges": 1320,
  "attached_graph_nodes": 1079,
  "candidate_rows": 13833,
  "category_counts": {
    "architecture_related": 669,
    "dataset_source": 13139,
    "keyword_related": 6,
    "likely_direct_recovery": 19
  },
  "high_value_count": 3083,
  "high_value_graph_nodes_added": 500,
  "keyword_counts": {
    "100m": 55,
    "agentkernel": 25,
    "agentkernel_lite": 4,
    "codegraph": 6,
    "model_stack": 4,
    "program_graph": 5,
    "repo_graph": 5,
    "seq2seq": 63
  }
}
```
