# Stage8628 Preserved 100M Manifest Recovery

This stage recovers preserved AgentKernel Lite 100M seq2seq manifest metadata from `/arxiv`. It does not load weights, run models, copy checkpoints, or authorize training.

## Recovered Model Shape

- model family: `agentkernel_lite_encdec_v1`
- parameter count: `102654362`
- preset: `agentkernel-lite-100m`
- d_model: `640`
- d_ff: `2048`
- layers: `6`
- heads: `10`
- vocab size: `1506`
- max position embeddings: `4096`
- dtype: `bfloat16`
- positional: `apply_rotary`
- rope theta: `1000000.0`
- agent policy heads: `true`
- agent intent labels: `18`
- agent controller dim: `128`
- tokenizer: `agentkernel-bpe`

## Recovered Bundles

- `pocketpal_controller_100m_stage972_stage968_kbpp_smoke_v415`: steps=20 last_loss=7.297492980957031 eval_points=2
- `pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415`: steps=None last_loss=None eval_points=0
- `pocketpal_controller_100m_stage1074_direct_answer_decoder_v415`: steps=120 last_loss=0.3782004415988922 eval_points=3
- `pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415`: steps=500 last_loss=0.5197105407714844 eval_points=5

## Replaced Surfaces

- `agent_intent_policy`
- `chat_decision_generation`
- `context_grounded_reply_generation`
- `controller_action_validity_estimation`
- `controller_confidence_estimation`
- `controller_latent_state_sidecar`
- `controller_ood_estimation`
- `controller_state_sketch_training`
- `controller_verification_need_estimation`
- `neural_retrieval_doc_embedding`
- `neural_retrieval_query_embedding`
- `retrieval_namespace_policy`

## Recovered Dataset Paths

### Train
- `/data/agentkernel-seq2seq-text-lab/runs/local/tmp/stage960_relation_qslot_hardened_surface/stage819_hardened_train.jsonl`
- `runs/local/artifacts/stage1072_direct_answer_dataset/agentkernel_lite_encdec_train.jsonl`

### Eval
- `/data/agentkernel-seq2seq-text-lab/runs/local/tmp/stage960_relation_qslot_hardened_surface/stage819_hardened_eval.jsonl`
- `runs/local/artifacts/stage1072_direct_answer_dataset/agentkernel_lite_encdec_eval.jsonl`

## Important Interpretation

- These are old preserved metadata and weight references, not current authorization to run them.
- The old direct-answer decoder runs are historically useful, but current research moved to structured policy, repo graph, bounded decoder, and verifier repair.
- The model config should guide trainer reconstruction, but future training must use current loss masks, judge routes, deterministic budget gates, and telemetry contracts.

## Metrics

```json
{
  "checkpoint_weight_references": 4,
  "eval_dataset_paths_recovered": 2,
  "freeze_patterns": {
    "encoder=False decoder=False tok=False": 1,
    "encoder=False decoder=True tok=True": 1,
    "encoder=None decoder=None tok=None": 1,
    "encoder=True decoder=False tok=False": 1
  },
  "manifest_paths_expected": 4,
  "manifest_paths_missing": 0,
  "manifest_paths_recovered": 4,
  "model_families": {
    "agentkernel_lite_encdec_v1": 4
  },
  "parameter_counts": {
    "102654362": 4
  },
  "presets": {
    "None": 1,
    "agentkernel-lite-100m": 3
  },
  "replaced_surface_count": 12,
  "train_dataset_paths_recovered": 2
}
```
