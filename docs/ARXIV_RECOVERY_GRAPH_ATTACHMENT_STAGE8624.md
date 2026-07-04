# Stage8624 `/arxiv` Recovery Graph Attachment

This stage attaches durable `/arxiv` recovery sources to the central research graph and prepares a longevity documentation bundle. It does not run models, load checkpoints, delete files, or authorize training.

## Session Archive

- root: `/arxiv/code/sessions`
- backup manifests: 4
- session JSONL files: 741
- session JSONL bytes: 7037033151
- latest backup manifest reports missing_count: 0
- latest backup manifest reports destination_file_count: 741

## Preserved Seq2Seq Storage

- root: `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab`
- exists: True
- records: 28
- manifests: 4
- checkpoint references: 9

## Likely Software Dataset Roots

- `/arxiv/datasets/11-47--gods_universe_codex_distill_god_seed_25k`
- `/arxiv/datasets/AletheiaResearch--GPT-5.3-Codex-Spark-Codex`
- `/arxiv/datasets/Crownelius--Complete-FABLE.5-traces-2M`
- `/arxiv/datasets/Glint-Research--Complete-FABLE.5-traces-2M`
- `/arxiv/datasets/ScaleAI--SWE-Atlas-QnA`
- `/arxiv/datasets/ajibawa-2023--Software-Architectural-Frameworks`
- `/arxiv/datasets/ajibawa-2023--Software-Architecture`
- `/arxiv/datasets/attentionAllYouNeed--Vibe-Coding-Claude-Fable-5`
- `/arxiv/datasets/google--code_x_glue_cc_clone_detection_big_clone_bench`
- `/arxiv/datasets/google--code_x_glue_cc_clone_detection_poj104`
- `/arxiv/datasets/google--code_x_glue_cc_cloze_testing_all`
- `/arxiv/datasets/google--code_x_glue_cc_cloze_testing_maxmin`
- `/arxiv/datasets/google--code_x_glue_cc_code_completion_line`
- `/arxiv/datasets/google--code_x_glue_cc_code_completion_token`
- `/arxiv/datasets/google--code_x_glue_cc_code_refinement`
- `/arxiv/datasets/google--code_x_glue_cc_code_to_code_trans`
- `/arxiv/datasets/google--code_x_glue_cc_defect_detection`
- `/arxiv/datasets/google--code_x_glue_ct_code_to_text`
- `/arxiv/datasets/google--code_x_glue_tc_nl_code_search_adv`
- `/arxiv/datasets/google--code_x_glue_tc_text_to_code`
- `/arxiv/datasets/google--code_x_glue_tt_text_to_text`
- `/arxiv/datasets/lazarus19--Vibe-Coding-Instruct-V2`
- `/arxiv/datasets/microsoft--codexglue_method_generation`
- `/arxiv/datasets/nampdn-ai--tiny-codes`
- `/arxiv/datasets/nvidia--Open-SWE-Traces`
- `/arxiv/datasets/nvidia--OpenCodeInstruct`
- `/arxiv/datasets/nvidia--OpenCodeReasoning`
- `/arxiv/datasets/paperbd--paper_instructions_300K-v1`

## Longevity Bundle

- local bundle: `/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage8624_arxiv_recovery_graph_attachment/longevity_docs_bundle`
- `/arxiv` mirror: `/arxiv/agentkernel_recovery/stage8624_central_graph_recovery`

## Metrics

```json
{
  "arxiv_mirror_written": true,
  "attached_graph_edges": 755,
  "attached_graph_nodes": 543,
  "latest_session_manifest_missing_count": 0,
  "likely_software_dataset_count": 28,
  "preserved_seq2seq_checkpoint_references": 9,
  "preserved_seq2seq_manifest_paths": 4,
  "preserved_seq2seq_records": 28,
  "session_backup_manifest_count": 4,
  "session_jsonl_bytes": 7037033151,
  "session_jsonl_count": 741,
  "top_level_arxiv_dataset_count": 42
}
```

## Recovery Use

Use these sources to recover exact old session passages, preserved 100M config/checkpoint metadata, and dataset roots. Checkpoints remain references only until explicit future execution/training gates pass.
