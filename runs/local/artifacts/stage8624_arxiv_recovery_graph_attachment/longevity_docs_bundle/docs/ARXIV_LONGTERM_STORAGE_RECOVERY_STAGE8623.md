# Stage8623 `/arxiv` Long-Term Storage Recovery

This is a targeted inventory of durable `/arxiv` locations that may contain old sessions, ledgers, manifests, trainer configs, checkpoint metadata, and research-spine material. It records paths and metadata only. It does not copy checkpoints, run models, or authorize training.

## Target Roots

- `/arxiv/code/sessions`: exists=True, files_seen=745, records_kept=4, truncated=False
- `/arxiv/preserved_checkpoints_20260609`: exists=True, files_seen=129, records_kept=104, truncated=False
- `/arxiv/TOLBERT_BRAIN`: exists=True, files_seen=74, records_kept=8, truncated=False
- `/arxiv/repositories/TOLBERT`: exists=True, files_seen=54, records_kept=1, truncated=False
- `/arxiv/repositories/tolbert-brain`: exists=True, files_seen=41, records_kept=0, truncated=False

## Counts By Class

- `candidate_recovery_file`: 1
- `checkpoint_metadata`: 11
- `checkpoint_or_weight`: 96
- `manifest`: 9

## Counts By Root

- `/arxiv/TOLBERT_BRAIN`: 8
- `/arxiv/code/sessions`: 4
- `/arxiv/preserved_checkpoints_20260609`: 104
- `/arxiv/repositories/TOLBERT`: 1

## High-Value Recovered Paths

- `checkpoint_or_weight` `/arxiv/TOLBERT_BRAIN/checkpoints/tolbert_brain/retrieval_cache/paper_spans_joint_mapped__tolbert_epoch3.pt`
- `checkpoint_or_weight` `/arxiv/TOLBERT_BRAIN/checkpoints/tolbert_brain/tolbert_epoch1.pt`
- `checkpoint_or_weight` `/arxiv/TOLBERT_BRAIN/checkpoints/tolbert_brain/tolbert_epoch1_baseline.pt`
- `checkpoint_or_weight` `/arxiv/TOLBERT_BRAIN/checkpoints/tolbert_brain/tolbert_epoch2.pt`
- `checkpoint_or_weight` `/arxiv/TOLBERT_BRAIN/checkpoints/tolbert_brain/tolbert_epoch3.pt`
- `checkpoint_or_weight` `/arxiv/TOLBERT_BRAIN/checkpoints/tolbert_brain/tolbert_epoch4.pt`
- `checkpoint_or_weight` `/arxiv/TOLBERT_BRAIN/checkpoints/tolbert_brain/tolbert_epoch5.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v470_v469_domaincontent_micro_lr1e8/model_q4_24to4_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v470_v469_domaincontent_micro_lr1e8/model_q4_24to4_best_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v470_v469_domaincontent_micro_lr1e8/model_q4_24to4_best_val_quality.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v470_v469_domaincontent_micro_lr1e8/model_q4_24to4_best_val_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v470_v469_domaincontent_micro_lr1e8/model_q4_24to4_last.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v470_v469_domaincontent_micro_lr1e8/model_q4_24to4_step_1.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v470_v469_domaincontent_micro_lr1e8/model_q4_24to4_step_2.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v470_v469_domaincontent_micro_lr1e8/model_q4_24to4_step_3.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v470_v469_domaincontent_micro_lr1e8/model_q4_24to4_step_4.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v471_v469_gentext_micro_lr1e8/model_q4_24to4_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v471_v469_gentext_micro_lr1e8/model_q4_24to4_best_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v471_v469_gentext_micro_lr1e8/model_q4_24to4_best_val_quality.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v471_v469_gentext_micro_lr1e8/model_q4_24to4_best_val_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v471_v469_gentext_micro_lr1e8/model_q4_24to4_last.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v471_v469_gentext_micro_lr1e8/model_q4_24to4_step_1.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v471_v469_gentext_micro_lr1e8/model_q4_24to4_step_2.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_best_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_best_val_quality.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_best_val_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_last.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_step_12.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_step_15.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_step_18.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_step_3.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_step_6.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v472_v327_broad_librispeech_articulation/model_q4_24to4_step_9.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v473_v320_stable_broad_micro/model_q4_24to4_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v473_v320_stable_broad_micro/model_q4_24to4_best_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v473_v320_stable_broad_micro/model_q4_24to4_best_val_quality.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v473_v320_stable_broad_micro/model_q4_24to4_best_val_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v473_v320_stable_broad_micro/model_q4_24to4_last.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v473_v320_stable_broad_micro/model_q4_24to4_step_3.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v473_v320_stable_broad_micro/model_q4_24to4_step_6.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v474_v390_broad_energy_content_guard/model_q4_24to4_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v474_v390_broad_energy_content_guard/model_q4_24to4_best_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v474_v390_broad_energy_content_guard/model_q4_24to4_best_val_quality.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v474_v390_broad_energy_content_guard/model_q4_24to4_best_val_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v474_v390_broad_energy_content_guard/model_q4_24to4_step_3.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v475_v390_broad_energy_content_guard_noheldoutleak/model_q4_24to4_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v475_v390_broad_energy_content_guard_noheldoutleak/model_q4_24to4_best_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v475_v390_broad_energy_content_guard_noheldoutleak/model_q4_24to4_best_val_quality.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v475_v390_broad_energy_content_guard_noheldoutleak/model_q4_24to4_best_val_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v475_v390_broad_energy_content_guard_noheldoutleak/model_q4_24to4_last.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v475_v390_broad_energy_content_guard_noheldoutleak/model_q4_24to4_step_12.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v475_v390_broad_energy_content_guard_noheldoutleak/model_q4_24to4_step_3.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v475_v390_broad_energy_content_guard_noheldoutleak/model_q4_24to4_step_6.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-acoustic-generation-lab/runs/checkpoints/f5tts_q4_4step_v475_v390_broad_energy_content_guard_noheldoutleak/model_q4_24to4_step_9.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1074_direct_answer_decoder_v415/checkpoints/step_00000120.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1074_direct_answer_decoder_v415/model/model.safetensors`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/checkpoints/step_00000500.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/model/model.safetensors`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage972_stage968_kbpp_smoke_v415/checkpoints/step_00000020.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage972_stage968_kbpp_smoke_v415/model/model.safetensors`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415/model/model.safetensors`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage1028_100m_schema_count_teacher_finetune_state.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage1029_100m_schema_count_preserve_finetune_state.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_4step_cfg2_clean360_progressive_v0_v461_reground_8to4_broad_clean360/model_q4_8to4_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_4step_cfg2_clean360_progressive_v0_v461_reground_8to4_broad_clean360/model_q4_8to4_last.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_4step_cfg2_clean360_progressive_v0_v461_reground_8to4_broad_clean360/model_q4_8to4_step_20.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_from8_quantstep_clean_v30_3090/phase_0001/model_q4_12to4_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_from8_quantstep_clean_v30_3090/phase_0001/model_q4_12to4_last.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_from_v10_scale_refine_v31_3090/phase_0001/model_q4_12to4_last.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_normgen_text_contrast_v34/model_q4_24to6_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_normgen_text_contrast_v34/model_q4_24to6_best_val_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_normgen_text_contrast_v34/model_q4_24to6_last.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_normgen_text_contrast_v34/model_q4_24to6_step_160.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_normgen_text_contrast_v34/model_q4_24to6_step_240.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_normgen_text_contrast_v34/model_q4_24to6_step_80.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_normgen_wide_text_contrast_v35/model_q4_24to6_best.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_normgen_wide_text_contrast_v35/model_q4_24to6_best_val_rollout.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_normgen_wide_text_contrast_v35/model_q4_24to6_step_60.pt`
- `checkpoint_or_weight` `/arxiv/preserved_checkpoints_20260609/data/transformer_10/checkpoints/f5tts_q4_6step_teacher24_speechtext_cache_v32c/model_q4_24to6_best.pt`

## Metrics

```json
{
  "checkpoint_or_weight_paths": 96,
  "classes": {
    "candidate_recovery_file": 1,
    "checkpoint_metadata": 11,
    "checkpoint_or_weight": 96,
    "manifest": 9
  },
  "existing_roots": 5,
  "files_seen": 1043,
  "keyword_totals": {
    "100m": 33,
    "agentkernel": 70,
    "checkpoint": 18,
    "decoder": 102,
    "encdec": 19,
    "manifest": 14,
    "pocketpal": 30,
    "runtime": 4,
    "seq2seq": 25,
    "stage": 56
  },
  "ledger_paths": 0,
  "manifest_paths": 9,
  "records_by_root": {
    "/arxiv/TOLBERT_BRAIN": 8,
    "/arxiv/code/sessions": 4,
    "/arxiv/preserved_checkpoints_20260609": 104,
    "/arxiv/repositories/TOLBERT": 1
  },
  "records_kept": 117,
  "target_roots": 5,
  "trainer_script_or_config_paths": 0
}
```

## Next Step

Attach selected high-value paths to the central research graph as recovery-source nodes and use them to rebuild missing manifest builders or trainer contracts. Keep checkpoint paths as references only until an explicit execution/training gate is passed.
